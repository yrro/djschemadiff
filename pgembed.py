'''Poor man's embedded PostgreSQL server.'''

import os, os.path
import sys

_postgres_bin = '/usr/lib/postgresql/8.1/bin'
_postgres_user = 'pgembed'

def initdb ():
	'''Creates a PostgreSQL cluster and returns the directory it is in.'''
	# TODO: use subprocess module, send output to stderr
	import tempfile
	dir = tempfile.mkdtemp ()
	initdb_path = os.path.join (_postgres_bin, 'initdb')
	status = os.spawnl (os.P_WAIT, initdb_path, initdb_path, '-U', _postgres_user, '-D', dir)
	if status != 0:
		rmdb (dir)
		raise Exception ('initdb failed (%i)' % (status))
	
	cfg = open (os.path.join (dir, 'postgresql.conf'), 'a')
	cfg.write ("listen_addresses = ''") # disable TCP, avoid port conflicts
	cfg.close ()
	return dir

def spawn_postmaster (db):
	'''Spawns a postmaster instance for the database in the background.
	Returns the pid of the process.'''
	postmaster_path = os.path.join (_postgres_bin, 'postmaster')
	pid = os.spawnl (os.P_NOWAIT, postmaster_path, postmaster_path, '-k', db, '-D', db, '-F')
	
	import atexit
	atexit.register (kill_postmaster, pid)
	
	return pid

def connect (db):
	'''Connects to the database at the specified directory.
	The connection is tried five times, at one-second intervals
	to allow for postmaster's initialisation process to complete.'''
	con = None
	saved_e = None
	import psycopg
	for x in xrange (0, 5):
		try:
			con = psycopg.connect ('host=%s user=%s dbname=postgres' % (db, _postgres_user))
		except psycopg.OperationalError, e:
			saved_e = e
		if con != None:
			break
		import time
		time.sleep (1)
	if con == None:
		raise saved_e
	return con

def kill_postmaster (pid):
	'''Terminates the postmaster instance'''
	import errno

	# check if the process is running: <http://www.erlenstar.demon.co.uk/unix/faq_2.html#SEC18>
	try:
		os.kill (pid, 0)
	except OSError, (e, msg):
		if e == errno.ESRCH:
			return
		raise e

	sys.stderr.write ('... sending postmaster the termination signal\n')
	# XXX: how do we know that pid is really our child?
	#      catch SIGCHLD? <http://www.erlenstar.demon.co.uk/unix/faq_8.html#SEC83>
	#      can also do away with the above check...
	try:
		import signal
		os.kill (pid, signal.SIGTERM)
	except OSError, (e, msg):
		# the process might have died since the last check
		if e != errno.ESRCH:
			raise e

	sys.stderr.write ('... waiting for process %i to terminate\n' % (pid))
	os.waitpid (pid, 0)
	sys.stderr.write ('... it is done, yuri!\n')

def rmdb (db):
	'''Deletes the database at the specified directory'''
	import shutil
	shutil.rmtree (db)

def pg_dump (host, user=_postgres_user, dbname='postgres', port='', password=''):
	'''Dumps the schema of a database'''
	# TODO: specify password to pg_dump with PGPASSWORD
	# environment var via subprocess module
	p = os.popen ('pg_dump --no-owner --schema-only --no-privileges --host=%s --username=%s --port=%s %s' % (host, user, port, dbname), 'r')
	output = p.read ()
	status = p.close ()
	if status != None:
		raise Exception ('pg_dump failed (%i)' % status)
	return output
