#!/usr/bin/python

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

import os, sys
from sets import Set as set

def syncdb (db):
	from django.conf import settings
	(old_ENGINE, old_NAME, old_USER, old_PASSWORD, old_HOST, old_PORT) = (settings.DATABASE_ENGINE, settings.DATABASE_NAME, settings.DATABASE_USER, settings.DATABASE_PASSWORD, settings.DATABASE_HOST, settings.DATABASE_PORT)

	settings.DATABASE_ENGINE = 'postgresql'
	settings.DATABASE_NAME = 'postgres'
	settings.DATABASE_USER = pgembed._postgres_user
	settings.DATABASE_PASSWORD = ''
	settings.DATABASE_HOST = db
	settings.DATABASE_PORT = '5432'
	
	import django.core.management
	try:
		django.core.management.syncdb (verbosity = 1, interactive = False)
	except TypeError:
		django.core.management.syncdb ()

	(settings.DATABASE_ENGINE, settings.DATABASE_NAME, settings.DATABASE_USER, settings.DATABASE_PASSWORD, settings.DATABASE_HOST, settings.DATABASE_PORT) = (old_ENGINE, old_NAME, old_USER, old_PASSWORD, old_HOST, old_PORT)

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

	# Get a copy of a clean database
	sql_clean = None

	import pgembed
	db = pgembed.initdb ()
	pid = pgembed.spawn_postmaster (db)
	try:
		try:
			# wait for the database to come up
			con = pgembed.connect (db)
			con.close ()

			syncdb (db)
			sql_clean = pgembed.pg_dump (host=db)

		except Exception, e:
			print '-' * 80
			import traceback
			traceback.print_exc ()
	finally:
		pgembed.kill_postmaster (pid)
		pgembed.rmdb (db)
	
	if sql_clean == None:
		sys.stderr.write ('Unable to create a fresh copy of the database.\n')
		sys.exit (1)

	# Get a copy of the current database
	from django.conf import settings
	if settings.DATABASE_ENGINE not in ('postgresql', 'postgresql_psycopg2'):
		sys.stderr.write ('Database engine "%s" is not yet supported.\n' % settings.DATABASE_ENGINE)
		sys.exit (1)
	
	sql_current = pgembed.pg_dump (user=settings.DATABASE_USER,
		dbname=settings.DATABASE_NAME,
		host=settings.DATABASE_HOST,
		port=settings.DATABASE_PORT,
		password=settings.DATABASE_PASSWORD)

	# Compare the two schemas
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
