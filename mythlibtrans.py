#!/usr/bin/env python2.7

from MythTV import Job, Recorded, System, MythDB, MythBE, MythError, MythLog
import sys, os, errno
import logging, logging.handlers
from optparse import OptionParser

LIBDIR = ['/home/mythtv/recordings/Episodes', '/home/mythtv/recordings/Movies', '/home/mythtv/recordings/Showings']
LOGFILE = '/home/mythtv/mythtranscode.log'
MAXLOGSIZE = 5 * 1024 * 1024
MAXLOGS = 1

class lib_listing:
	def __init__(self, listing):
		self.listing = listing
		self.symlink = os.readlink(listing)

	def dump(self):
		logging.debug("%s: [%s]" % (self.listing, self.symlink))

def transcode(jobid=None, chanid=None, starttime=None):
        ' connect to mythtv database '
        db = MythDB()
        be = MythBE(db=db)

	logging.info("start transcode")

	if jobid:
		job = Job(jobid, db=db)
		chanid = job.chanid
		starttime = job.starttime
		logging.info("%s" % jobid)
		logging.info("%s" % chanid)
		logging.info("%s" % starttime)
	rec = Recorded((chanid, starttime), db=db)
	' TODO: get the starttime into the correct format (from 20150827014200 to 2015-08-27 00:42:00-06:00)'

	' loop all files in lib_dir that are symlinks and find the one that matches this recording '
        for ld in LIBDIR:
                for dp, dn, files in os.walk(ld):
                        for file in files:
                                filepath = os.path.join(dp,file)
                                if (os.path.islink(filepath)):
                                        logging.debug("%s -> %s" % (filepath, os.readlink(filepath)))

	' do the transode '

	' update the database for the new file name '

	' update the symlink for the new file name '

def main():
	' setup logger, all to stdout and INFO and higher to LOGFILE '
	logging.basicConfig(format='%(message)s',
				level=logging.NOTSET)
	loggingfile = logging.handlers.RotatingFileHandler(LOGFILE, maxBytes=(MAXLOGSIZE), backupCount=MAXLOGS)
	loggingfile.setLevel(logging.INFO)
	formatter = logging.Formatter('%(asctime)s: %(message)s', datefmt='%m-%d %H:%M')
	loggingfile.setFormatter(formatter)
	logging.getLogger('').addHandler(loggingfile)

	parser = OptionParser(usage="usage: %prog [options] [jobid]")

	parser.add_option('--chanid', action='store', type='int', dest='chanid',
        	help='Use chanid for manual operation')
	parser.add_option('--starttime', action='store', type='int', dest='starttime',
        	help='Use starttime for manual operation')
	parser.add_option('-v', '--verbose', action='store', type='string', dest='verbose',
        	help='Verbosity level')

	opts, args = parser.parse_args()

	if opts.verbose:
        	if opts.verbose == 'help':
            		print "TODO help text" 
            		sys.exit(0)

	if len(args) == 1:
		logging.info("transcode with jobid[%s]" % args[0])
		transcode(jobid=args[0])
	elif opts.chanid and opts.starttime:
		logging.info("transdoe with chanid[%s], starttime[%s]" % (opts.chanid, opts.starttime))
		transcode(chanid=opts.chanid, starttime=opts.starttime)
	else:
		print "Script must be provided jobid, or chanid and starttime."
		sys.exit(1)

if __name__ == '__main__':
	main()
