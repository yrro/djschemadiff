#!/usr/bin/python

# model objects
#

class SqlIndex (object):
	def __init__ (self, name, unique, table, method, expression):
		self.name = name
		self.unique = unique
		self.table = table
		self.method = method
		self.expression = expression
	
	def __str__ (self):
		result = 'CREATE '
		if self.unique: result += 'UNIQUE '
		result += 'INDEX %s ON %s USING %s (%s)' % (self.name, self.table, self.method, self.expression)
		return result

class SqlForeignConstraint (object):
	def __init__ (self, name, reftable, refcolumn, deferrable, initdeferred):
		self.name = name
		self.reftable = reftable
		self.refcolumn = refcolumn
		self.deferrable = deferrable
		self.initdeferred = initdeferred
	
	def __str__ (self):
		result = 'FOREIGN KEY (%s) REFERENCES %s(%s)' % (self.name, self.reftable, self.refcolumn)
		if self.deferrable: result += ' DEFERRABLE'
		if self.initdeferred: result += ' INITIALLY DEFERRED'
		return result

class SqlPrimaryConstraint (object):
	def __init__ (self, name):
		self.name = name
	
	def __str__ (self):
		return 'PRIMARY KEY (%s)' % (self.name)

class SqlUniqueConstraint (object):
	def __init__ (self, columns):
		self.columns = columns
	
	def __str__ (self):
		return 'UNIQUE (%s)' % (', '.join (self.columns))

class SqlCheckConstraint (object):
	def __init__ (self, expression):
		self.expression = expression
	
	def __str__ (self):
		return 'CHECK (%s)' % (self.expression)

class SqlConstraint (object):
	def __init__ (self, name, constraint):
		self.name = name
		self.constraint = constraint
	
	def __str__ (self):
		return 'CONSTRAINT %s %s' % (self.name, self.constraint)

class SqlAlterTable (object):
	def __init__ (self, name, only, constraint):
		self.name = name
		self.only = only
		self.constraint = constraint
	
	def __str__ (self):
		result = 'ALTER TABLE '
		if self.only: result += 'ONLY '
		result += '%s ADD %s' % (self.name, self.constraint)
		return result

class SqlTableField (object):
	def __init__ (self, name, type, null):
		self.name = name
		self.type = type
		self.null = null
	
	def __str__ (self):
		result = '%s %s ' % (self.name, self.type)
		if not self.null: result += 'NOT '
		result += 'NULL'
		return result

class SqlCreateTable (object):
	def __init__ (self, name, properties):
		self.name = name
		self.properties = properties
	
	def __str__ (self):
		return 'CREATE TABLE %s (%s)' % (self.name, ', '.join ([str (p) for p in self.properties]))

class SqlSet (object):
	def __init__ (self, name, value):
		self.name = name
		self.value = value
	
	def __str__ (self):
		return 'SET %s = %s' % (self.name, ','.join (self.value))

class SqlComment (object):
	pass

# lexer rules
#

keywords = ['SET', 'COMMENT', 'CREATE', 'TABLE', 'NOT', 'NULL', 'ON', 'SCHEMA', 'IS', 'ALTER', 'ONLY', 'ADD', 'CONSTRAINT', 'UNIQUE', 'PRIMARY', 'KEY', 'CHECK', 'DEFERRABLE', 'DEFERRED', 'FOREIGN', 'INDEX', 'INITIALLY', 'REFERENCES', 'USING', 'BEGIN', 'COMMIT']

tokens = keywords + ['sqlcomment', 'NEWLINE', 'ID', 'QID', 'NUMBER', 'GEQ', 'STRING']
literals = ';(),='

def t_NEWLINE (t):
	r'\n+'
	t.lexer.lineno += len (t.value)

def t_sqlcomment (t):
	r'--.*'
	pass

t_ignore = '\t '

# operators
t_GEQ = '>='

# literals
def t_STRING (t):
	"'.*?'"
	t.value = t.value[1:-1]
	return t

def t_NUMBER (t):
	'[0-9]+'
	t.value = int (t.value)
	return t

# identifiers
def t_ID (t):
	'[a-zA-Z][a-zA-Z0-9_]*'
	if t.value in keywords:
		t.type = t.value
	else:
		t.type = 'ID'
	return t

def t_QID (t):
	'"([a-zA-Z][a-zA-Z0-9_]*)"'
	# quoted identifier: strip quotes, and treat as an ID
	t.type = 'ID'
	t.value = t.value[1:-1]
	return t

def t_error (t):
	raise lex.LexError ("Illegal character on line %d at: %s" % (t.lineno, t.value.split ('\n')[0]), None)

# grammar rules
#

def p_statements_multi (p):
	'statements : statements statement'
	p[0] = p[1] + [p[2]]

def p_statements_single (p):
	'statements : statement'
	p[0] = [p[1]]

def p_statement (p):
	'''statement : set_stmt ';'
	             | comment_stmt ';'
	             | create_table_stmt ';'
	             | alter_table_stmt ';'
	             | create_index_stmt ';'
	'''
	p[0] = p[1]

def p_set_stmt (p):
	'''set_stmt : SET ID '=' set_values'''
	p[0] = SqlSet (name=p[2], value=p[4])

def p_set_values_multi (p):
	'''set_values : set_values ',' set_value'''
	p[0] = p[1] + [p[3]]

def p_set_values_single (p):
	'set_values : set_value'''
	p[0] = [p[1]]

def p_set_value (p):
	'''set_value : ID
	             | NUMBER'''
	p[0] = p[1]
	
def p_set_value_quoted (p):
	'set_value : STRING'
	p[0] = "'%s'" % (p[1])

def p_comment_stmt (p):
	'comment_stmt : COMMENT ON SCHEMA ID IS STRING'
	p[0] = SqlComment ()

def p_create_table_stmt (p):
	'''create_table_stmt : CREATE TABLE ID '(' table_properties ')' '''
	p[0] = SqlCreateTable (name=p[3], properties=p[5])

def p_table_properties_multi (p):
	'''table_properties : table_properties ',' table_property'''
	p[0] = p[1] + [p[3]]

def p_table_properties_single (p):
	'table_properties : table_property'
	p[0] = [p[1]]

def p_table_property (p):
	'''table_property : table_field
	                  | constraint'''
	p[0] = p[1]

def p_expression_paren (p):
	'''expression : '(' expression ')' '''
	p[0] = '(%s)' % (p[2])

def p_expression_op (p):
	'''expression : expression operator expression'''
	p[0] = '%s %s %s' % (p[1], p[2], p[3])

def p_expression_atom (p):
	'''expression : NUMBER
	              | ID'''
	p[0] = p[1]

def p_operator (p):
	'''operator : GEQ'''
	p[0] = p[1]

def p_table_field (p):
	'table_field : ID field_type opt_null'
	p[0] = SqlTableField (name=p[1], type=p[2], null=p[3])

def p_field_type_multi (p):
	'field_type : field_type field_type_word'
	p[0] = '%s %s' % (p[1], p[2])

def p_field_type_single (p):
	'field_type : field_type_word'''
	p[0] = p[1]

def p_field_type_word_id (p):
	'field_type_word : ID'
	p[0] = p[1]

def p_field_type_word_sized (p):
	'''field_type_word : ID '(' NUMBER ')' '''
	p[0] = '%s (%i)' % (p[1], p[3])

def p_opt_null (p):
	'''opt_null : NULL'''
	p[0] = True

def p_opt_not_null (p):
	'''opt_null : NOT NULL
	            | '''
	p[0] = False

def p_alter_table_stmt (p):
	'alter_table_stmt : ALTER TABLE opt_only ID ADD constraint'
	p[0] = SqlAlterTable (name=p[4], only=p[3], constraint=p[6])

def p_opt_only (p):
	'opt_only : ONLY'
	p[0] = True

def p_opt_only_empty (p):
	'opt_only : '
	p[0] = False

def p_constraint (p):
	'''constraint : CONSTRAINT ID check_constraint
	              | CONSTRAINT ID unique_constraint
				  | CONSTRAINT ID primary_constraint
				  | CONSTRAINT ID foreign_constraint'''
	p[0] = SqlConstraint (p[2], p[3])

def p_check_constraint (p):
	'''check_constraint : CHECK '(' expression ')' '''
	p[0] = SqlCheckConstraint (p[3])

def p_unique_constraint (p):
	'''unique_constraint : UNIQUE '(' id_list ')' '''
	p[0] = SqlUniqueConstraint (p[3])

def p_primary_constraint (p):
	'''primary_constraint : PRIMARY KEY '(' ID ')' '''
	p[0] = SqlPrimaryConstraint (p[4])

def p_foreign_constraint (p):
	'''foreign_constraint : FOREIGN KEY '(' ID ')' REFERENCES ID '(' ID ')' opt_deferrable opt_initdeferred'''
	p[0] = SqlForeignConstraint (name=p[4], reftable=p[7], refcolumn=p[9], deferrable=p[11], initdeferred=p[12])

def p_opt_deferrable (p):
	'opt_deferrable : DEFERRABLE'
	p[0] = True

def p_opt_deferrable_empty (p):
	'opt_deferrable :'
	p[0] = False

def p_opt_initdeferred (p):
	'opt_initdeferred : INITIALLY DEFERRED'
	p[0] = True

def p_opt_initdeferred_empty (p):
	'opt_initdeferred :'
	p[0] = False

def p_id_list_multi (p):
	'''id_list : id_list ',' ID'''
	p[0] = p[1] + [p[3]]

def p_id_list_single (p):
	'id_list : ID'
	p[0] = [p[1]]

def p_create_index_stmt (p):
	'''create_index_stmt : CREATE opt_unique INDEX ID ON ID USING index_method '(' expression ')' '''
	p[0] = SqlIndex (name=p[4], unique=p[2], table=p[6], method=p[8], expression=p[10])

def p_opt_unique (p):
	'opt_unique : UNIQUE'
	p[0] = True

def p_opt_unique_empty (p):
	'opt_unique : '
	p[0] = False

def p_index_method (p):
	'index_method : ID'
	p[0] = p[1]

from ply import lex, yacc
lex.lex ()
yacc.yacc ()

def parse (sql):
	'''Parses semicolon-delimeted statements in the input string. Returns a
	list of Sql* objects.'''
	return yacc.parse (sql)

if __name__ == '__main__':
	import sys
	for x in parse (sys.stdin.read ()):
		print x
