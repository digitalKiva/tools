#! /usr/bin/env python

import os, sys
import xml.etree.cElementTree as ET
from lxml import etree as ET2
import xml.dom.minidom as dom
import urllib2
import re
#import logging
import argparse
import requests
import json
#from tvdb_client.clients.ApiV2Client import ApiV2Client
from tvdbclient.tvdbclient import TVDBClient
from moviedb.moviedb import MovieDBClient

# script version information
version_major = 1
version_minor = 7
print("\n== %s (v%d.%d) ==" % (__file__, version_major, version_minor))

# configure arument options
parser = argparse.ArgumentParser()
parser.add_argument("-u", "--url", dest="mythtv_url", help="URL for the mythtv backend database", required=True)
parser.add_argument("-d", "--dest", dest="pool_dir", help="Location for the linked videos", required=True)
parser.add_argument("-p", "--port", dest="mythtv_port", help="Port for the mythtv backend database", default="6544")
parser.add_argument("-a", "--add", dest="new_rec", help="Path to new mythtv recording to be processed")
parser.add_argument("-s", "--scan", dest="scan_rec", help="mythtv recording directory to process all files");
args = parser.parse_args()

# sanity check some of the config options
if (args.new_rec is None and args.scan_rec == False) or (args.new_rec is not None and args.scan_rec == True):
	print "Must specify either --add or --scan"
	sys.exit()
if args.mythtv_url is None:
	print "Must specify a mythtv URL (--url)"
	sys.exit()

# define program constants
POOL_DIR = args.pool_dir

# define program globals
__tvdbclient__ = None
__moviedbclient__ = None

##
# Define the Recording class.  Holds all the information for a Mythtv recording
class Recording(object):
	def __init__(self, recordingXML):
		self.recordingXML = recordingXML
		self.filename = self.recordingXML.find('Recording/FileName').text
		self.recgroup = self.recordingXML.find('Recording/RecGroup').text
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
	def inetref_num(self):
		try:
			ret = int(self.inetref_split()[2])
		except ValueError:
			ret = None
		return ret

	def is_special(self):
		return self.is_movie() == False and self.season.zfill(2) == "00"

	def is_movie(self):
		res = False
		if self.cattype == 'movie' or (self.cattype == 'None' and self.programid[:2] == 'MV'):
			res = True
		return res

	def safe_title(self):
		return re.sub('[\[\]/\\;><&*:%=+@!#^()|?\'"]', '', self.title)

##
# Lookup in the .specialinfo file the episode number for this special
# Return: if True then episode is matching episode
#  if False, then episode is max in file + 1
def __get_special_episode(path, recording):
	episode = 0
	file = path + "/.specialinfo"
	found = False
	# look for episode in the file
	if os.path.isfile(file):
		with open(file) as f:
			for line in f:
				special = line.strip().split('|')
				episode = special[1]
				if special[0] == recording.programid:
					found = True
					break

	episode = int(episode)
	if not found:
		episode = episode + 1

	print " - Special episode info (found:"+str(found)+") ["+recording.programid+" | ep: "+str(episode)+"]"

	return (found, episode)

##
# return the year only given a date "<year>-<month>-<day>"
def __get_year(date):
	return date.split("-")[0]

##
# update the .specialinfo file with the episode number for this special recording
def __update_special_episode(path, recording):
	file = path + "/.specialinfo"

	(found, episode) = __get_special_episode(path, recording)
	if not found:
		print " - Add special episode info [%s | ep: %s]" % (recording.programid, recording.episode)
		with open(file, 'a+') as f:
			f.write("%s|%s\n" % (recording.programid, recording.episode))

##
# Write the shows series info into nfo_file
def __write_series_nfo(recording, nfo_file):
	site = None
	inetref = None
	if recording.inetref != None and recording.inetref != 'None':
		(site, sep, inetref) = recording.inetref_split()
		# print "%s = %s|%s|%s" % (recording.inetref, site, sep, inetref)
		if inetref == "None":
			inetref = None

	root = ET2.Element('tvshow')
	title = ET2.SubElement(root, 'title')
	title.text = recording.title
	# only include the following items if there is no inetref info
	if not inetref:
		showtitle = ET2.SubElement(root, 'showtitle')
		showtitle.text = recording.title

	ET2.ElementTree(root).write(nfo_file, pretty_print=True, encoding='UTF-8', xml_declaration=True)

	# there was a vaid inetref, so put the url at the end of the file
	if inetref:
		with open(nfo_file, "a") as f:
			if not site or site == "ttvdb.py":
				# print "http://thetvdb.com/?tab=series&id=%s" % inetref
				f.write("http://thetvdb.com/?tab=series&id=%s\n" % inetref)
			else:
				print "WARNING: Unknown reference [%s|%s]" % (site, inetref)
				#TODO how to resolve this, call this function again with cleared inetref?

	return

##
# Write show episode info into nfo_file
def __write_episode_nfo(recording, nfo_file):
	root = ET2.Element('episodedetails')
	title = ET2.SubElement(root, 'title')
	title.text = recording.subtitle
	showtitle = ET2.SubElement(root, 'showtitle')
	showtitle.text = recording.title
	if recording.is_special():
		season = ET2.SubElement(root, 'displayseason')
		season.text = '0'
		episode = ET2.SubElement(root, 'displayepisode')
		episode.text = recording.episode
	else:
		season = ET2.SubElement(root, 'season')
		season.text = recording.season
		episode = ET2.SubElement(root, 'episode')
		episode.text = recording.episode
	if recording.description != 'None':
		plot = ET2.SubElement(root, 'plot')
		plot.text = recording.description
	if recording.airdate != 'None':
		airdate = ET2.SubElement(root, 'aired')
		airdate.text = recording.airdate
	playcount = ET2.SubElement(root, 'playcount')
	playcount.text = '0'

	ET2.ElementTree(root).write(nfo_file, pretty_print=True, encoding='UTF-8', xml_declaration=True)

	# TODO
	# add actor information
	#<actor>
    # <name>Little Suzie</name>
    # <role>Pole Jumper/Dancer</role>
    #</actor>
	# TODO: put show specific url at the end of the file

	return

##
# Write nfo file in the movie format
def __write_movie_nfo(recording, nfo_file):
	site = None
	inetref = None
	if recording.inetref != None and recording.inetref != 'None':
		(site, sep, inetref) = recording.inetref_split()
		# print "%s = %s|%s|%s" % (recording.inetref, site, sep, inetref)
		if inetref == "None":
			inetref = None

	root = ET2.Element('movie')
	title = ET2.SubElement(root, 'title')
	title.text = recording.title

    # only include the following items if there is no inetref info
	if not inetref:
		if recording.description != 'None':
			plot = ET2.SubElement(root, 'plot')
    		plot.text = recording.description
		if recording.category != 'None':
			genre = ET2.SubElement(root, 'genre')
			genre.text = recording.category
		if recording.airdate != 'None':
			year = ET2.SubElement(root, 'year')
			year.text = recording.airdate[:4]

	ET2.ElementTree(root).write(nfo_file, pretty_print=True, encoding='UTF-8', xml_declaration=True)

    # there was a vaid inetref, so put the url at the end of the file
	if inetref:
		with open(nfo_file, "a") as f:
			if not site or site == "tmdb3.py":
				# print "http://themoviedb.org/movie/%s" % inetref
				f.write("http://themoviedb.org/movie/%s\n" % inetref)
			else:
				print "Unknown reference [%s|%s]" % (site, inetref)
                #TODO how to resolve this, call this function again with cleared inetref?

	# https://api.themoviedb.org/3/movie/10681?api_key=8c65f4f3b0d3c59203ca6b62039426b1
	return

##
# write show / movie nfo file information in the passed in nfo_file
def __write_nfo(recording, nfo_file):
	if recording.is_movie():
		xmltree = __write_movie_nfo(recording, nfo_file)
	else:
		xmltree = __write_episode_nfo(recording, nfo_file)
	return

##
# Format an xml element to be more human readable
def __print_pretty_xml(xml_element):
	rough_string = ET.tostring(xml_element, 'utf-8')
	reparsed = dom.parseString(rough_string)
	return reparsed.toprettyxml(indent="\t")

##
# Return the file name of a full path
# Return "file" w/ path = "/var/lib/file.ts"
def __base_filename(path):
	return os.path.splitext(os.path.basename(path))[0]

##
# Return file extension of passed in file (.mpg)
def __file_extension(file):
	splitext = os.path.splitext(file)
	if len(splitext) == 2:
		return splitext[1]
	else:
		print "Error: no extension found (%s)" % file
		return ""

##
# Returns movie / episode path attached to base_path
# <pool_dir>/movies
# <pool_dir>/episodes
def __kodi_category_path(base_path, recording):
	return os.path.join(base_path, 'movies' if recording.is_movie() else 'episodes')

##
# Returns movie / episode specific path based on recording type
# <pool_dir>/movies/<movie>
# <pool_dir>/episodes/<show>
def __kodi_show_path(base_path, recording):
	return os.path.join(__kodi_category_path(base_path, recording), recording.safe_title())

##
# Returns a full kodi compatible link path for the mythtv_recording
# <pool_dir>/movies/True Grit/True Grit.ts
# <pool_dir>/episodes/Mr. Robot/Season 2/Mr. Robot S02E09 (eps2.7init5.fve).ts
def __kodi_full_path(base_path, mythtv_rec):
	# get the series specific part of the path
	series_path = mythtv_rec.safe_title()
	if not mythtv_rec.is_movie():
		series_path = "Season " + mythtv_rec.season + "/" + mythtv_rec.safe_title()
		series_path += " S" + mythtv_rec.season.zfill(2) + "E" + mythtv_rec.episode.zfill(2)
		series_path += " (" + mythtv_rec.subtitle + ")"
	return os.path.join(__kodi_show_path(base_path, mythtv_rec), series_path) + __file_extension(mythtv_rec.filename)

##
# Looks up the entire mythtv recording list
def __get_recording_list(base_url):
	url = base_url + '/Dvr/GetRecordedList'
	print " - Getting MythTV recording list: " + url
	treeroot = ET.parse(urllib2.urlopen(url)).getroot()
	#print __print_pretty_xml(treeroot)
	return treeroot

##
# Find the inetref ID for a movie or show series from online json results
#  Either validate the mythtv recording inetref or gather it from online
def __validate_inetref(json_results, mythtv_rec):
	data_key = ["results", "data"]
	title_key = ["title", "seriesName"]
	date_key = ["release_date", "firstAired"]
	id_key = ["id", "id"]
	key_index = 0
	if not mythtv_rec.is_movie():
		key_index = 1

	# filter the results to only those with exact matching titles
	title_filter = []
	for item in json_results[data_key[key_index]]:
		# remove any non alpha-numeric characters from string to aid in searching
		json_title = re.sub('[^0-9a-zA-Z]+', '', item[title_key[key_index]])
		mythtv_title = re.sub('[^0-9a-zA-Z]+', '', mythtv_rec.title)
		# print "%s vs %s" % (json_title.lower(), mythtv_title.lower())
		if json_title.lower() == mythtv_title.lower():
			title_filter.append(item)

	if len(title_filter) == 0:
		print " - title filter too strict, restore and re-filter"
		title_filter = json_results[data_key[key_index]]

	# print "=== json_results ==="
	# print json.dumps(json_results, indent=True)
	# print "=== title_filter ==="
	# print json.dumps(title_filter, indent=True)

	if len(title_filter) >= 2:
		# if we have more then 1 result then further filter
		# create new array of all items in title_filter that don't have a year date mathing the mythtv_rec
		title_filter[:] = [item for item in title_filter \
					       if __get_year(item[date_key[key_index]]) ==  __get_year(mythtv_rec.airdate)]

	if len(title_filter) >= 2:
		if mythtv_rec.is_movie():
			# further filter based on highest rated movie
			print " - movie extra-filter using highest rating"
			high_rate = 0
			save_item = title_filter[0]
			for item in title_filter:
				if int(item["vote_count"]) > high_rate:
					high_rate = int(item["vote_count"])
					save_item = item
			del title_filter[:]
			title_filter.append(save_item)

		else:
			print "WARNING: non-movie extra-filter not supported"

	if len(title_filter) != 1:
		# TODO: log this as an error
		print "WARNING: unable to filter the json resuts (%d)" % len(title_filter)
		# print json.dumps(json_results, indent=True)
		print "=== title_filter ==="
		print json.dumps(title_filter, indent=True)
	else:
		# we successfully filterd down to a single result
		online_inet = title_filter[0][id_key[key_index]]
		mythtv_inet = mythtv_rec.inetref_num()
		if online_inet == mythtv_inet:
			# TODO: log that we have validated our inetref
			print " - Validated inetref online (%d) matches recording (%d)" % (online_inet, mythtv_inet)
		else:
			# TODO: replace our inetref with online one
			print " - Replacing recording inetref (" + str(mythtv_inet) + ") with online (" + str(online_inet) + ")"
			mythtv_rec.inetref = unicode(online_inet)

	return mythtv_rec

def __validate_episode_info(mythtv_rec):
	found = False
	keep_searching = True
	page = 1
	mythtv_episode = re.sub('[^0-9a-zA-Z]+', '', mythtv_rec.subtitle)
	# print "Searching for episode (%s) in series (%s)[%s]" % (mythtv_rec.subtitle, mythtv_rec.title, mythtv_rec.inetref)
	while keep_searching:
		search_resp = __tvdbclient__.get_series_episodes(mythtv_rec.inetref_num(), page)
		if search_resp != None:
			#print json.dumps(search_resp, indent=True)
			# look for our recording in the results
			for item in search_resp["data"]:
				try:
					json_episode = re.sub('[^0-9a-zA-Z]+', '', item["episodeName"])
				except:
					json_episode = ""
				# print "%s vs %s" % (json_episode.lower(), mythtv_episode.lower())
				if json_episode.lower() == mythtv_episode.lower():
					found = True
					json_season = unicode(item["airedSeason"])
					json_episode = unicode(item["airedEpisodeNumber"])
					if json_season != mythtv_rec.season or json_episode != mythtv_rec.episode:
						print " - Replacing recording episode info (%s.%s) with online (%s.%s)" % (mythtv_rec.season, mythtv_rec.episode, json_season, json_episode)
						mythtv_rec.season = unicode(json_season)
						mythtv_rec.episode = unicode(json_episode)
					else:
						print " - Validated online season/episode matches recording (%s.%s)" % (mythtv_rec.season, mythtv_rec.episode)
					keep_searching = False
					break
			page = page + 1
		else:
			# we have failed or reach the end
			keep_searching = False

	if not found:
		print " - WARNING: episode (%s) not found in series (%s)[%s] on tvdb" % (mythtv_rec.subtitle, mythtv_rec.title, mythtv_rec.inetref)

	return mythtv_rec

##
# Create the video symlink in the pool_dir and create .nfo
# For tvshows create the .nfo file from tvdb
# for movies create the .nfo file from
#  Based on this: http://kodi.wiki/view/NFO_files/movies#Movie_tags
def __process_recording(pool_dir, new_rec, mythtv_rec):
	print " - Processing [" + new_rec + "]"

	# look up the information online
	search_resp = None
	debug_print = ""
	if mythtv_rec.is_movie():
		search_resp = __moviedbclient__.search_movie(name=mythtv_rec.title)
		debug_print = "MovieDB movie"
	else:
		search_resp = __tvdbclient__.search_series(name=mythtv_rec.title)
		debug_print = "TVDB series"

	if search_resp != None:
		#print json.dumps(search_resp, indent=True)
		mythtv_rec = __validate_inetref(search_resp, mythtv_rec)
	else:
		print " - WARNING: %s search results failed" % debug_print

	# ensure the episode information is correct
	if not mythtv_rec.is_movie():
		mythtv_rec = __validate_episode_info(mythtv_rec)

	# create symlink directory
	link = __kodi_full_path(pool_dir, mythtv_rec)

	# if this is a special epsiode and it does not have a episode number
	#  we need to lookup the next episode number based on the above path and refresh the path
	if mythtv_rec.is_special() and mythtv_rec.episode.zfill(2) == "00":
		(found, s_episode) = __get_special_episode(os.path.dirname(link), mythtv_rec)
		mythtv_rec.episode = unicode(str(s_episode))
		link = __kodi_full_path(pool_dir, mythtv_rec)

	# create link if it doesnt already exist
	if not os.path.exists(os.path.dirname(link)):
		os.makedirs(os.path.dirname(link))
	if not os.path.exists(link) and not os.path.islink(link):
		print " - Linking [" + new_rec + "] => [" + link.encode('ascii', 'replace') + "]"
		os.symlink(new_rec, link)

	# only write the series nfo for non-movies
	if not mythtv_rec.is_movie():
		nfo_file = os.path.join(__kodi_show_path(args.pool_dir, mythtv_rec), 'tvshow.nfo')
		if not os.path.isfile(nfo_file):
			print " - Writing tvshow.nfo [" + nfo_file + "]"
			__write_series_nfo(mythtv_rec, nfo_file)

	# create movie/episode nfo file (only for movies and special episodes)
	#  let kodi get the real episode information itself (from title, season and episode #)
	if mythtv_rec.is_movie() or mythtv_rec.is_special():
		nfo_file = os.path.splitext(link)[0] + '.nfo'
		print " - Writing .nfo file [" + nfo_file.encode('ascii', 'replace') + "]"
		__write_nfo(mythtv_rec, nfo_file)
	else:
		print " - Skipping writing .nfo file for real episode"

	# ensure this recording special episode number is recorded
	if mythtv_rec.is_special():
		__update_special_episode(os.path.dirname(link), mythtv_rec)
		# print "link (updated): " + link

	# ensure proper permissions
	print " - Validating permissions: " + __kodi_category_path(pool_dir, mythtv_rec)
	print " - Validating permissions: " + __kodi_show_path(pool_dir, mythtv_rec)
	os.chmod(__kodi_category_path(pool_dir, mythtv_rec), 0775)
	os.chmod(__kodi_show_path(pool_dir, mythtv_rec), 0775)
	for root, dirs, files in os.walk(__kodi_show_path(pool_dir, mythtv_rec)):
		for name in files:
			# print(os.path.join(root, name))
			os.chmod(os.path.join(root, name), 0775)
		for name in dirs:
			# print(os.path.join(root, name))
			os.chmod(os.path.join(root, name), 0775)

	return

##
# Takes as input either a file or directory.  If it is a file then add the single file
# otherwise if it is a directory scan the directory for all video files
def scan_recording(mythtv_url, new_files):
	file_list = []

	print "Processing [" + new_files + "]..."

	if os.path.isfile(new_files):
		# if the argument is a file then create a list of one file
		# print " - single file mode"
		file_list.append(new_files)
	elif os.path.exists(new_files):
		# if the argument is a directory, scan the directory for mpg, mp4, ts and create list
		extensions = [".mpg", ".mp4", ".ts"]
		print " - directory scan mode"
		for f in os.listdir(new_files):
			if __file_extension(f) in extensions:
				file_list.append(os.path.join(new_files, f))
	else:
		# else return error
		print "Error: [" + new_files + "] not a directory or file"
		return

	recording_list = __get_recording_list(mythtv_url)

	# loop over each recording to be processed, finding it's entry in the mythtvDB
	for new_rec in file_list:
		found = False
		for mythtv_entry in recording_list.iter('Program'):
			mythtv_rec = Recording(mythtv_entry)
			# only all default recording group (no "live tv" or "deleted")
			if not mythtv_rec.recgroup == 'Default':
				continue
			if __base_filename(new_rec) == __base_filename(mythtv_rec.filename):
				print "Found new recording [" + __base_filename(new_rec) + "] in mythtv DB"
				#mythtv_rec.printy()
				__process_recording(args.pool_dir, new_rec, mythtv_rec)
				found = True
				continue
		if not found:
			print " - Recording [" + __base_filename(new_rec) + "] not found in mythtv DB!"

		# ttvdb_key = "A3F61578CF5DDBF3": (try below without en.zip too)
			# (example: http://www.thetvdb.com/api/A3F61578CF5DDBF3/series/276812/all/en.zip)
		# tmdb_key = "8c65f4f3b0d3c59203ca6b62039426b1"
		# for wall-e: https://api.themoviedb.org/3/movie/10681?api_key=8c65f4f3b0d3c59203ca6b62039426b1
	return

def main():
	global __tvdbclient__
	global __moviedbclient__
	__tvdbclient__ = TVDBClient(username='joseph.swantek@gmail.com',\
								api_key='A3F61578CF5DDBF3', account_identifier='AFD0E726C193F34F')
	__tvdbclient__.login()
	if not __tvdbclient__.is_authenticated:
		print "* TVDB is NOT authenticated!"

	__moviedbclient__ = MovieDBClient(api_key='8c65f4f3b0d3c59203ca6b62039426b1')
	__moviedbclient__.login()
	if not __moviedbclient__.is_authenticated:
		print "* MovieDB is NOT authenticated!"

	mythtv_url = "http://" + args.mythtv_url + ":" + args.mythtv_port

	if args.scan_rec:
		scan_recording(mythtv_url, args.scan_rec)
	elif args.new_rec:
		scan_recording(mythtv_url, args.new_rec)
	sys.exit(0)

main()
