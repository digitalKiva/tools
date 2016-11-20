#!/usr/bin/env python

#from MythTV import Job, Recorded, System, MythDB, MythBE, MythError, MythLog
import sys, os, errno
import xml.etree.cElementTree as ET
import urllib2
import logging, logging.handlers
from optparse import OptionParser

LIBDIR = ['/home/mythtv/recordings/episodes', '/home/mythtv/recordings/episodes_misc', '/home/mythtv/recordings/movies', '/home/mythtv/recordings/movies_misc']
LOGFILE = '/home/mythtv/mythsyncdeletes.log'
MAXLOGSIZE = 5 * 1024 * 1024
MAXLOGS = 1


class RecordingState:
	Recorded, Recording, BusyJob, Autoexpire = range(4)

class recording:
	def __init__(self, mythrec):
		self.mythrec = mythrec
		self.metadata = mythrec.exportMetadata()
		self.program = mythrec.getProgram()
		self.lib_listing = None
		self.state = RecordingState.Recorded

	def dump(self):
		logging.debug("%s: [%s][link: %s]" % (self.metadata.filename, self.state, self.lib_listing))
		logging.debug(self.metadata)
		logging.debug(self.program)
		if self.lib_listing:
			self.lib_listing.dump()

	def match(self, filename):
		if (os.path.split(self.metadata.filename)[1] == os.path.split(filename)[1]):
			return True
		else:
			return False

class lib_listing:
	def __init__(self, listing):
		self.listing = listing
		self.symlink = os.readlink(listing)

	def dump(self):
		logging.debug("%s: [%s]" % (self.listing, self.symlink))

##
# Define the Recording class.  Holds all the information for a Mythtv recording
class Recording(object):
	def __init__(self, recordingXML):
		self.recordingXML = recordingXML
		self.filename = self.recordingXML.find('Recording/FileName').text
		self.recgroup = self.recordingXML.find('Recording/RecGroup').text
		self.recordid = self.recordingXML.find('Recording/RecordId').text
		self.title = unicode(self.recordingXML.find('Title').text)
		self.subtitle = unicode(self.recordingXML.find('SubTitle').text)
		self.season = unicode(self.recordingXML.find('Season').text)
		self.episode = unicode(self.recordingXML.find('Episode').text)
		self.airdate = unicode(self.recordingXML.find('Airdate').text)
		self.description = unicode(self.recordingXML.find('Description').text)
		self.category = unicode(self.recordingXML.find('Category').text)
		self.cattype = unicode(self.recordingXML.find('CatType').text)
		self.inetref = unicode(self.recordingXML.find('Inetref').text)
		self.seriesid = unicode(self.recordingXML.find('SeriesId').text)
		self.programid = unicode(self.recordingXML.find('ProgramId').text)
		self.special = self.is_movie() == False and self.season.zfill(2) == "00" and self.episode.zfill(2) == "00"
		self.lib_listing = None
		return

	def printy(self):
		print self.title.encode('ascii', 'replace') + ": " + self.subtitle.encode('ascii', 'replace')
		print "- Description [" + self.description + "]"
		print "- Season [" + self.season + "]"
		print "- Episode [" + self.episode + "]"
		print "- Air Date [" + self.airdate + "]"
		print "- Category Type [" + self.cattype + "]"
		print "- Category [" + self.category + "]"
		print "- Series ID [" + self.seriesid + "]"
		print "- Program ID [" + self.programid + "]"
		print "- InetRef [" + self.inetref + "]"
		print "- Filename [" + self.filename + "]"
		return

	# returns (site, sep, inetref) from ttvdb.py_289590
	def inetref_split(self):
		return self.inetref.rpartition("_")

	# returns just the number of hte inetref (9999 from tvdb.py_9999)
	def inetref_int(self):
		val = self.inetref_split()[2]
		if isinstance(val, int):
			return int(self.inetref_split()[2])
		else:
			return None

	def is_special(self):
		return self.special

	def is_movie(self):
		res = False
		if self.cattype == 'movie' or (self.cattype == 'None' and self.programid[:2] == 'MV'):
			res = True
		return res

	def safe_title(self):
		return re.sub('[\[\]/\\;><&*:%=+@!#^()|?\'"]', '', self.title)

	def filename_match(self, filename):
		if (os.path.split(self.filename)[1] == os.path.split(filename)[1]):
			return True
		else:
			return False

##
# Looks up the entire mythtv recording list
def __get_recording_list(base_url):
	url = base_url + '/Dvr/GetRecordedList'
	print " - Getting MythTV recording list: " + url
	treeroot = ET.parse(urllib2.urlopen(url)).getroot()
	#print __print_pretty_xml(treeroot)
	return treeroot

##
# Looks up the entire mythtv recording list
def __get_expiring_list(base_url):
	url = base_url + '/Dvr/GetExpiringList'
	print " - Getting MythTV expiring list: " + url
	treeroot = ET.parse(urllib2.urlopen(url)).getroot()
	#print __print_pretty_xml(treeroot)
	return treeroot

def main():
	' setup logger, all to stdout and INFO and higher to LOGFILE '
	logging.basicConfig(format='%(message)s',
				level=logging.NOTSET)
	loggingfile = logging.handlers.RotatingFileHandler(LOGFILE, maxBytes=(MAXLOGSIZE), backupCount=MAXLOGS)
	loggingfile.setLevel(logging.INFO)
	formatter = logging.Formatter('%(asctime)s: %(message)s', datefmt='%m-%d %H:%M')
	loggingfile.setFormatter(formatter)
	logging.getLogger('').addHandler(loggingfile)

	' connect to mythtv database '
#	db = MythDB()
#	be = MythBE(db=db)

	' loop all files in lib_dir that are symlinks and create listing '
	listings = []
	for ld in LIBDIR:
		for dp, dn, files in os.walk(ld):
			for file in files:
				filepath = os.path.join(dp,file)
				if (os.path.islink(filepath)):
					listings.append(lib_listing(filepath))


	mythtv_url = "http://192.168.2.102:6544"

	' get list of all recordings from MythDB, link with library, figure out their status '
	#recordings = []
	activeRecordings = []
	activeJobs = []
	newExpireList = []
	recording_list = __get_recording_list(mythtv_url)
	expiring_list = __get_expiring_list(mythtv_url)
	#mythrecordings = db.searchRecorded()
	#recorderList = be.getRecorderList()
	#for mrec in mythrecordings:
	recording_count = 0
	for mythtv_entry in recording_list.iter('Program'):
		recording_count = recording_count + 1
		mythtv_rec = Recording(mythtv_entry)
		#logging.debug()
		print "[%s][%s]" % (mythtv_rec.title, mythtv_rec.filename)
		#rec = recording(mrec)
		#recordings.append(rec)

		' skip items already set to autoexpire '
		expired = False
		for expired_entry in expiring_list.iter('Program'):
			expired_rec = Recording(expired_entry)
			if (mythtv_rec.filename == expired_rec.filename):
				print " - [%s] in expire list" % expired_rec.filename
				expired = True
				break
		if expired:
			logging.debug(" - already set to expire, skip")
			continue

		' loop through the list of library items looking for matching recordings, linking them '
		for l in listings:
			if mythtv_rec.filename_match(l.symlink):
				if mythtv_rec.lib_listing != None:
					logging.error("UH OH! Linking with something already linked!")
				else:
					mythtv_rec.lib_listing = l

		' figure out if the recording is active '
#		for recorder in recorderList:
#			arec = be.getCurrentRecording(recorder)
#			if (arec['title'] is not None) and (arec['chanid'] is not 0) and \
#			   (arec == rec.program):
#				logging.debug(" - currently recording, skip")
#				activeRecordings.append(rec)
#				rec.state = RecordingState.Recording
#				break
#		if (rec.state != RecordingState.Recorded):
#			continue

		' figuire if the recording is part of an active job '
#		jobs = db.searchJobs() #need to generate jobs on each loop
#		for job in jobs:
#			if job.status in [Job.ABORTING, Job.ERRORING, Job.PAUSED, Job.PENDING, \
#					  Job.QUEUED, Job.RETRY, Job.RUNNING, Job.STARTING, Job.STOPPING]:
#				jobrec = Recorded((job.chanid, job.starttime), db=db)
#				if rec.mythrec == jobrec:
#					logging.debug(" - currently part of a job, skip")
#					activeJobs.append(rec)
#					rec.state = RecordingState.BusyJob
#					break
#		if (rec.state != RecordingState.Recorded):
#			continue

		' potentially add to auto-expire list, and set orphaned recordings to auto-expire '
		#if (rec.lib_listing == None) and (rec.state == RecordingState.Recorded):
        if (mythtv_rec.lib_listing == None):
			logging.debug(" - no link, delete")
			newExpireList.append(mythtv_rec)
			# rec.mythrec.delete(force=True, rerecord=False)
			#rec.mythrec.autoexpire = 1
			#rec.mythrec.update()

	' log summary '
	logging.info("")
	logging.info("** Summary **")
	logging.info(" [MythDB Recordings][%s]" % recording_count)
	#logging.info("  - active recordings: %s" % len(activeRecordings))
	#for arec in activeRecordings:
	#	logging.info("   - %s [%s]" % (arec.program, arec.metadata.filename))
	#logging.info("  - in progress jobs: %s" % len(activeJobs))
	#for ajobs in activeJobs:
	#	logging.info("   - %s [%s]" % (ajobs.program, ajobs.metadata.filename))

	logging.info("")
	logging.info(" [Mythical Links][%s]" % len(listings))
	logging.info("  - new auto-expire items: %s" % len(newExpireList))
	for d in newExpireList:
		logging.info( "   - %s [%s]" % (d.title, d.filename))

if __name__ == '__main__':
	main()
