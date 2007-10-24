'''Poor man's embedded PostgreSQL server.'''

# djschemadiff - show differences between Django database schemas
# Copyright 2007 Sam Morris <sam@robots.org.uk>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os, os.path
import sys

_postgres_bin = '/usr/lib/postgresql/8.2/bin'
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
	cfg.write ("listen_addresses = ''\n") # disable TCP, avoid port conflicts
	cfg.write ("log_min_error_statement = error\n") # log SQL statements that cause errors
	#cfg.write ("log_min_duration_statement = 0\n") # log all SQL statements
	cfg.close ()
	return dir

def spawn_postmaster (db):
	'''Spawns a postmaster instance for the database in the background.
	Returns the pid of the process.'''
	postmaster_path = os.path.join (_postgres_bin, 'postmaster')
	pid = os.spawnl (os.P_NOWAIT, postmaster_path, postmaster_path, '-k', db, '-D', db, '-F')
	
	return pid

def connect (db):
	'''Connects to the database at the specified directory.
	The connection is tried five times, at one-second intervals
	to allow for postmaster's initialisation process to complete.'''
	try:
		import psycopg2
	except ImportError:
		import psycopg as psycopg2
	con = None
	saved_e = None
	for x in xrange (0, 5):
		try:
			con = psycopg2.connect ('host=%s user=%s dbname=postgres' % (db, _postgres_user))
		except psycopg2.OperationalError, e:
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

	sys.stderr.write ('... sending postmaster the Fast Shutdown signal\n')
	# XXX: how do we know that pid is really our child?
	#      catch SIGCHLD? <http://www.erlenstar.demon.co.uk/unix/faq_8.html#SEC83>
	#      can also do away with the above check...
	try:
		import signal
		os.kill (pid, signal.SIGINT)
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
	p = os.popen ('pg_dump --no-owner --schema-only --no-privileges --schema=public --host=%s --username=%s --port=%s %s' % (host, user, port, dbname), 'r')
	output = p.read ()
	status = p.close ()
	if status != None:
		raise Exception ('pg_dump failed (%i)' % status)
	return output
