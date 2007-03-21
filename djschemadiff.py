#!/usr/bin/python

import os, sys
from sets import Set as set

# It would be great if we could call django's own syncdb routine with our
# own database connection, but I can't work out how. So instead I copied
# the structure of the django.core.management.syncdb function.
def syncdb (connection):
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

if __name__ == '__main__':
	# Parse command line arguments
	import optparse
	op = optparse.OptionParser (usage = '%prog [options] settings_file')
	op.add_option ('--mode', '-m',
		dest='mode', choices=['udiff', 'vimdiff'], default='udiff',
		help='udiff (default) or vimdiff')
		
	(options, args) = op.parse_args()
	if len (args) != 1:
		op.error ('Specify the path to a single Django settings file')

	import os.path
	(settingspath, settingsmodule) = os.path.split (args[0])
	settingsmodule = os.path.splitext (settingsmodule)[0]

	# Init django database
	try:
		sys.path.insert (0, settingspath)
		# without including the parent directory, the imports silently fail
		sys.path.insert (0, settingspath + '/../')
		os.environ['DJANGO_SETTINGS_MODULE'] = settingsmodule
		from django.db import models
	except EnvironmentError, e:
		sys.stderr.write ('%s\n' % (e))
		sys.exit (1)

	import pgembed
	db = pgembed.initdb ()

	try:
		pid = pgembed.spawn_postmaster (db)
		con = pgembed.connect (db)

		syncdb (con)
		sql_clean = pgembed.pg_dump (host=db)

		con.close ()
		pgembed.kill_postmaster (pid)
	except Exception, e:
		print '-' * 80
		import traceback
		traceback.print_exc ()
		pgembed.rmdb (db)
		sys.exit (1)
	
	pgembed.rmdb (db)

	from django.conf import settings
	sql_current = pgembed.pg_dump (user=settings.DATABASE_USER,
		dbname=settings.DATABASE_NAME,
		host=settings.DATABASE_HOST,
		port=settings.DATABASE_PORT,
		password=settings.DATABASE_PASSWORD)

	import sqlparse
	sql_current = sqlparse.parse (sql_current)
	sql_clean = sqlparse.parse (sql_clean)

	def bytype (o1, o2):
		'Sort objects by their type; then by their value.'
		r = cmp (type (o1), type (o2))
		if r != 0:
			return r
		return cmp (o1, o2)
	sql_current.sort (bytype)
	sql_clean.sort (bytype)

	if options.mode == 'udiff':
		import difflib
		g = difflib.unified_diff ('\n'.join ([str (s) + ';' for s in sql_current]).split ('\n'),
			'\n'.join ([str (s) + ';' for s in sql_clean]).split ('\n'),
			fromfile='current-schema', tofile='new-schema',
			n=10, lineterm='')
		print '\n'.join (g)
	
	elif options.mode == 'vimdiff':
		import tempfile
		f1 = tempfile.NamedTemporaryFile ()
		f2 = tempfile.NamedTemporaryFile ()
		f1.write ('\n'.join ([str (s) + ';' for s in sql_current]))
		f2.write ('\n'.join ([str (s) + ';' for s in sql_clean]))
		f1.flush ()
		f2.flush ()
		os.spawnlp (os.P_WAIT, 'vimdiff', 'vimdiff', '-m', f1.name, f2.name)
