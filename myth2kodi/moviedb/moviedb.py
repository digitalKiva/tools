#! /usr/bin/env pythong

from datetime import datetime, timedelta
import json
import requests

class MovieDBClient(object):
	API_BASE_URL = 'https://api.themoviedb.org/3'
	TOKEN_DURATION_SECONDS = 23 * 3600  # 23 Hours
	TOKEN_MAX_DURATION = 24 * 3600  # 24 Hours

	def __init__(self, api_key):
		self.api_key = api_key
		self.is_authenticated = False

	def __get_header(self):
		header = dict()
		header['Content-Type'] = 'application/json'
		header['Accept'] = 'application/json'
		header['Connection'] = 'close'
		# header['User-Agent'] = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.11; rv:47.0) Gecko/20100101 Firefox/47.0'

		return header

	def login(self):
		auth_url = self.API_BASE_URL + '/authentication/token/new'
		auth_data = dict()
		auth_data['api_key'] = self.api_key

		auth_resp = requests.request('GET', auth_url, params=auth_data, data=None, headers=self.__get_header())
		#print auth_resp
		#print json.loads(auth_resp.content)

		if auth_resp.status_code == 200:
			auth_resp_data = json.loads(auth_resp.content)
			self.is_authenticated = True
		else:
			raise AuthenticationFailedException('Authentication failed!')

	def search_movie(self, name=None):
		#print "search_movie (name=%s)" % (name)

		if not self.is_authenticated:
			print "Error: can't search. Not authenticated."
			return

		search_url = self.API_BASE_URL + '/search/movie'
		search_data = dict()
		search_data['api_key'] = self.api_key
		search_data['language'] = 'en-US'
		search_data['query'] = name

		search_resp = requests.request('GET', search_url, params=search_data, data=None, headers=self.__get_header())

		if search_resp.status_code == 200:
			#print "search_movie success"
			return json.loads(search_resp.content)
		else:
			print "search_movie failure (%d) | url[%s] | data[%s] | name[%s]" % (search_resp.status_code, search_url, search_data, name)
			return
