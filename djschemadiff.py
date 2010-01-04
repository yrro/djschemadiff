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
from sets import Set as set # python 2.3 compat

import pgembed

def syncdb (db):
	from django.conf import settings
	new_settings = {'DATABASE_ENGINE': 'postgresql_psycopg2',
		'DATABASE_NAME': 'postgres',
		'DATABASE_USER': pgembed._postgres_user,
		'DATABASE_PASSWORD': '',
		'DATABASE_HOST': db,
		'DATABASE_PORT': 5432}

	old_settings = {}
	for name, value in new_settings.items ():
		old_settings[name] = getattr (settings, name)
		setattr (settings, name, value)

	import django.core.management
	try:
		django.core.management.call_command ('syncdb', verbosity = 1, interactive = False)
	except AttributeError:
		# django 0.96 fallback
		try:
			django.core.management.syncdb (verbosity = 1, interactive = False)
		except TypeError:
			# django 0.95 fallback
			django.core.management.syncdb ()

	for name, value in old_settings.items ():
		setattr (settings, name, value)

if __name__ == '__main__':
	# Parse command line arguments
	import optparse
	op = optparse.OptionParser (usage = '%prog [options] settings_file')
	op.add_option ('--mode', '-m',
		dest='mode', choices=['udiff', 'vimdiff'], default='udiff',
		help='udiff (default) or vimdiff')
	op.add_option ('--template', '-t',
		dest='template',
		help='file containing SQL statements to process before running syncdb')
		
	(options, args) = op.parse_args()
	if len (args) != 1:
		op.error ('Specify the path to a single Django settings file')

	import os.path
	if not os.path.exists (args[0]):
		op.error ('The settings file you specified does not exist.')
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

	db = pgembed.initdb ()
	pid = pgembed.spawn_postmaster (db)
	try:
		try:
			# wait for the database to come up
			con = pgembed.connect (db)
			con.close ()

			if options.template:
				pgembed.process_sql (db, options.template)

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

	if options.mode == 'udiff':
		import difflib
		g = difflib.unified_diff (sql_current.split ('\n'),
			sql_clean.split ('\n'),
			fromfile='current-schema', tofile='new-schema',
			n=10, lineterm='')
		print '\n'.join (g)
	
	elif options.mode == 'vimdiff':
		import tempfile
		f1 = tempfile.NamedTemporaryFile ()
		f2 = tempfile.NamedTemporaryFile ()
		f1.write (sql_current)
		f2.write (sql_clean)
		f1.flush ()
		f2.flush ()
		os.spawnlp (os.P_WAIT, 'vimdiff', 'vimdiff', '-m', f1.name, f2.name)

# vim: noet sts=0
