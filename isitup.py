#!/usr/bin/env python
import argparse, socket, sqlite3, sys, time, urllib2

"""
	IsItUp.py - Poll TCP ports for up/down states on a regular basis
	 This is intended to be called from crontab once per minute. Each time it
	 runs it queries the SQLite database, and determines which entries need to
	 be polled and which can wait. If an entry has not responded in the last
	 five minutes (configurable), it will be polled again every 60 seconds
	 (also configurable). Any entry that has responded within the last five
	 minutes will not be polled until the five minutes is up.

	 The code and the config settings in the database make use of the following
	 terms:
	 - check, occurs every five minutes, typically after a successful check
	 - recheck occurs once per minute, typically after a [re]check fails
"""

def log(msg):
	"Log a message to the console if the --verbose flag was used"
	if args.verbose:
		print(str(msg))

def checkDue(checktime, row):
	"Are we due for a normal check now?"
	rowid, host, port, address, lastup, lastcheck = row
	return checktime - lastcheck > checkinterval - offset

def recheckDue(checktime, row):
	"Are we due for a recheck now?"
	rowid, host, port, address, lastup, lastcheck = row
	return (checktime - lastcheck > recheckinterval - offset) and lastup + checkinterval < checktime - offset

def countdownDue(checktime, row):
	"Number of seconds remaining until the next check/recheck"
	rowid, host, port, address, lastup, lastcheck = row
	if isDown(checktime, row):
		return recheckinterval - (checktime - lastcheck)
	return checkinterval - (checktime - lastcheck)

def isUp(checktime, row):
	"Is the entry up? As defined by a successful check less than 5 minutes ago"
	rowid, host, port, address, lastup, lastcheck = row
	if checktime - lastup < checkinterval + offset:
		return True
	return False

def isDown(checktime, row):
	"Is the entry down? The opposite of isUp()"
	return not isUp(checktime, row)

def state(checktime, row):
	"Return a text state of UP or DOWN for a given entry"
	state = "DOWN"
	if isUp(checktime, row):
		state = "UP"
	return state

def checkRow(checktime, row):
	"Check an entry and see if it's up"
	rowid, host, port, address, lastup, lastcheck = row

	# Log some information to the screen
	log("Service:   %s:%i" % (host, port))
	log("Address:   " + address)

	# Attempt to connect to the host
	s = None
	for res in socket.getaddrinfo(host, port, socket.AF_UNSPEC, socket.SOCK_STREAM):
		af, socktype, proto, canonname, sa = res
		try:
			s = socket.socket(af, socktype, proto)
		# Failure before we opened the socket
		except socket.error as msg:
			s = None
			continue
		try:
			s.connect(sa)
		# Failure opening the socket
		except socket.error as msg:
			s.close()
			s = None
			continue
		break
	# If we failed to open the socket successfully
	if s is None:
		# Note it as down for the user
		log("Status:    DOWN")
		log("LASTUP:    " + str(lastup))
		# Update the database to indicate we tried
		c.execute("UPDATE checks SET LASTCHECK = %i WHERE ID = %i" % (checktime, rowid))
		conn.commit()
	# It's up!
	else:
		# Read any data the socket wants to send, then close the connection
		data = s.recv(1024)
		s.close()
		# Log the status for the user
		log("Status:    UP")
		log("LASTUP:    " + str(checktime))
		# Update the database
		c.execute("UPDATE checks SET LASTUP = %i, LASTCHECK = %i WHERE ID = %i" % (checktime, checktime, rowid))
		conn.commit()
		# Retrieve the corresponding URL
		try:
			response = urllib2.urlopen(address)
			html = response.read()
		# Failure to retrieve URL, warn user and move on
		except Exception:
			log("WARNING:   failed to retrieve page from URL." % (rowid, host, port, address))
			pass
	# Display final information about this specific check for the user
	log("LASTCHECK: " + str(checktime))
	log("")

def removeCheck(conn, c, check):
	"Remove a check from the database"
	# Convert our check ID to an integer
	check = int(check)
	# We don't do negative numbers
	if check < 0:
		print("Error: You must specify a positive check to remove")
		exit(1)
	# Retrieve the record for the check in question
	c.execute("SELECT * FROM checks WHERE ID = %i" % check)
	data = c.fetchall()
	# Was any data returned?
	if len(data) == 0:
		print("There is no check by that ID.")
		exit(1)
	# Load the data from the DB results
	rowid, host, port, address, lastup, lastcheck = data[0]
	# Delete the DB record
	c.execute("DELETE FROM checks WHERE ID = %i" % check)
	conn.commit()
	# Display the results
	print("Check [%i] %s:%i, (%s) has been removed." % (rowid, host, port, address))
	return

def listChecks(conn, c):
	"List all checks in the database"
	# Fetch all rows from the DB
	c.execute("SELECT * FROM checks")
	rows = c.fetchall()
	if not len(rows):
		print("There are no records in the database.")
		exit()
	# Go through each row, display it on the screen
	for row in rows:
		rowid, host, port, address, lastup, lastcheck = row
		print("[%i] %s:%i, (%s) is %s" % (rowid, host, port, address, state(int(time.time()), row)))

def addCheck(conn, c, host, port, url):
	"Add a check to the database"
	# Insert the new check into the database
	c.execute("INSERT INTO checks (host, port, URL, LASTUP, LASTCHECK) VALUES ('%s', %s, '%s', 0, 0)" % (host, port, url))
	conn.commit()
	# Determine the rowid (ID field) for the new DB record
	c.execute("SELECT last_insert_rowid()")
	# Retrieve the new record
	c.execute("SELECT * FROM checks WHERE ID = %i" % c.fetchone()[0])
	rowid, host, port, address, lastup, lastcheck = c.fetchone()
	# Display it on the screen
	print("Check [%i] %s:%i, (%s) has been added." % (rowid, host, port, address))

"""
	START THE PROGRAM
"""

# Configure the argument parser
# TODO: Can we adjust groupings and set things like exclusivity and
# 		 requirements? it would be nice if that were displayed for --help
#		 instead of this twisty maze of error messages further below
parser = argparse.ArgumentParser()
parser.add_argument("--check", help="Run the availability check", action="store_true")
parser.add_argument("--verbose", help="Display information while running", action="store_true")
parser.add_argument("--list", help="List the checks in the database", action="store_true")
parser.add_argument("--remove-check", help="Remove the specified check from the database", action="store", dest="remove_check")
parser.add_argument("--add-check", help="Add a check to the database", action="store_true")
parser.add_argument("--host", help="The hostname of the entry to add", action="store", dest="host")
parser.add_argument("--port", help="The port of the entry to add", action="store", dest="port")
parser.add_argument("--url", help="The URL of the entry to add", action="store", dest="url")
args = parser.parse_args()

# Make sure required parameters exist
if not args.check and not args.list and not args.remove_check and not args.add_check:
    print("You must specify either --check, --list --add-check or --remove-check")
    exit(1)

## Check for incompatible parameters
if args.check and (args.list or args.add_check or args.remove_check):
	print("You can only use --check in conjunction with --verbose")
	exit(1)

if args.list and (args.check or args.add_check or args.remove_check):
	print("You cannot use --list with any other arguments")
	exit(1)

if args.remove_check and (args.check or args.list or args.add_check):
	print("You cannot use --remove-check with any other arguments")
	exit(1)

if args.add_check and (args.check or args.list or args.remove_check):
	print("You cannot use --add-check with any aguments beyond --host, --port, and --url")
	exit(1)

if args.add_check and (not args.host or not args.port or not args.url):
	print("The arguments --host, --port, and --url are mandatory when using --add-check")
	exit(1)

# Open the database
conn = sqlite3.connect("isitup.db")
c = conn.cursor()

# Create the settings table if necessary
c.execute('''CREATE TABLE IF NOT EXISTS settings
			 (checkinterval INTEGER, recheckinterval INTEGER, offset INTEGER)
          ''')

# Populate the settings table with defaults if it's empty
c.execute("SELECT * FROM settings")
settings = c.fetchall()
if len(settings) == 0:
	c.execute("INSERT INTO settings VALUES (300, 60, 10)")
	conn.commit()
	c.execute("SELECT * FROM settings")
	settings = c.fetchall()

# Load the settings from the DB results
checkinterval, recheckinterval, offset = settings[0]

# Create the checks table if necessary
c.execute('''CREATE TABLE IF NOT EXISTS checks
			 (id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT UNIQUE,
              host TEXT,
			  port INTEGER,
              URL TEXT,
			  LASTUP INTEGER,
              LASTCHECK INTEGER)
          ''')

# Are we supposed to be removing an entry instead of running?
if args.remove_check:
	removeCheck(conn, c, args.remove_check)
	exit()

# Are we supposed to be displaying a list instead of running?
if args.list:
	listChecks(conn, c)
	exit()

# Are we suppoed to be adding an entry to the list instead of running?
if args.add_check:
	addCheck(conn, c, args.host, args.port, args.url)
	exit()

# Retrieve all the rows to be checked
c.execute("SELECT * FROM checks")
rows = c.fetchall()

# Record the timestamp we will use for this session
checktime = int(time.time())

# Loop through the rows of checks to be performed
for row in rows:
	# Load the data from the DB results (row)
	rowid, host, port, address, lastup, lastcheck = row

	# Is it due to be checked?
	if checkDue(checktime, row) or recheckDue(checktime, row):
		checkRow(checktime, row)
	# If not, log the countdown and state
	else:
		log("- Skipping [%i] %s:%i, due in %i seconds (%s)" % (rowid, host, port, countdownDue(checktime, row), state(checktime, row)))

conn.close()
