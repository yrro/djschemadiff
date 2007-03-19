#!/usr/bin/python

import os, sys
from sets import Set as set

postgres_bin = '/usr/lib/postgresql/8.1/bin'

def initdb ():
	'''Creates a PostgreSQL cluster and returns the directory it is in.'''
	import tempfile
	dir = tempfile.mkdtemp ()
	initdb_path = os.path.join (postgres_bin, 'initdb')
	status = os.spawnl (os.P_WAIT, initdb_path, initdb_path, '-U', 'theuser', '-D', dir)
	if status != 0:
		rmdb (dir)
		raise Exception ('initdb failed (%i)' % (status))
	return dir

def spawn_postmaster (db):
	'''Spawns a postmaster instance for the database in the background. Returns the pid of the process.'''
	postmaster_path = os.path.join (postgres_bin, 'postmaster')
	return os.spawnl (os.P_NOWAIT, postmaster_path, postmaster_path, '-k', db, '-D', db, '-F')

def syncdb (connection):
	'''Code structure taken from django.core.management.syncdb'''
	from django.db import models
	import django.core.management
	from django.core.management import _get_sql_model_create, _get_sql_for_pending_references, _get_many_to_many_sql_for_model, get_sql_indexes_for_model

	django.core.management.disable_termcolors ()
	cursor = connection.cursor ()

	seen_models = set ()
	pending_references = {}

	for app in models.get_apps ():
		app_name = app.__name__.split ('.')[-2]
		model_list = models.get_models (app)

		for model in model_list:
			print '... processing %s.%s model' % (app_name, model._meta.object_name)
			sql, references = _get_sql_model_create (model, seen_models)
			seen_models.add (model)
			for refto, refs in references.items ():
				pending_references.setdefault (refto, []).extend (refs)
			sql.extend (_get_sql_for_pending_references (model, pending_references))
			print '... creating table %s' % model._meta.db_table
			for statement in sql:
				cursor.execute (statement)
			
		for model in model_list:
			sql = _get_many_to_many_sql_for_model (model)
			if sql:
				print '... creating m2m tables for %s.%s model' % (app_name, model._meta.object_name)
			for statement in sql:
				cursor.execute (statement)

		connection.commit ()
		
	for app in models.get_apps ():
		app_name = app.__name__.split ('.')[-2]
		for model in models.get_models (app):
			index_sql = get_sql_indexes_for_model (model)
			if index_sql:
				print '... installing index for %s.%s model' % (app_name, model._meta.object_name)
			for sql in index_sql:
				cursor.execute (sql)
	
	connection.commit ()

def kill_postmaster (pid):
	print '... sending postmaster the termination signal'
	# XXX: how do we know that pid is our child?'''
	import signal
	os.kill (pid, signal.SIGTERM)
	print '... waiting for process %i to terminate' % (pid)
	os.waitpid (pid, 0)
	print '... it is done, yuri!'

def rmdb (db):
	import shutil
	shutil.rmtree (db)

if __name__ == '__main__':
	import traceback
	db = initdb ()
	cfg = open ('%s/postgresql.conf' % (db), 'a')
	cfg.write ('listen_addresses = \'\'')
	cfg.close ()

	try:
		pid = spawn_postmaster (db)

		try:
			# connect
			con = None
			ex = None
			for x in xrange (0, 5):
				import psycopg
				try: con = psycopg.connect ('host=%s dbname=postgres user=theuser' % (db))
				except psycopg.OperationalError, e: 	ex = e
				if con != None:
					break
				import time
				time.sleep (1)
			if con == None:
				raise ex

			# do stuff
			syncdb (con)

			p = os.popen ('pg_dump --no-owner --schema-only --no-privileges --host=%s -U theuser postgres' % (db), 'r')
			sql_clean = p.readlines ()
			status = p.close ()
			if status != None:
				raise Exception ('... pg_dump failed (%i)' % status)

		except Exception, e:
			print '-' * 80
			traceback.print_exc ()

		if con != None:
			con.close ()
		kill_postmaster (pid)
	except Exception, e:
		print '-' * 80
		traceback.print_exc ()
	
	rmdb (db)

	from django.conf import settings
	p = os.popen ('pg_dump --no-owner --schema-only --no-privileges -U %(user)s %(db)s' % {'user': settings.DATABASE_USER, 'db': settings.DATABASE_NAME}, 'r')
	sql_current = p.readlines ()
	status = p.close ()
	if status != None:
		raise Exception ('... pg_dump failed (%i)' % status)

	import difflib
	g = difflib.unified_diff (sql_current, sql_clean, fromfile='current-schema', tofile='new-schema')
	print ''.join (g)
