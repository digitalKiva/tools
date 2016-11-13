#! /usr/bin/env python

from datetime import datetime, timedelta
import json
import requests

class TVDBClient(object):
	API_BASE_URL = 'https://api.thetvdb.com'
	TOKEN_DURATION_SECONDS = 23 * 3600  # 23 Hours
	TOKEN_MAX_DURATION = 24 * 3600  # 24 Hours

	def __init__(self, username, api_key, account_identifier):
		self.username = username
		self.api_key = api_key
		self.account_identifier = account_identifier
		self.is_authenticated = False
		self.__token = None
		self.__auth_time = 0

	def __get_header(self):
		header = dict()
		header['Content-Type'] = 'application/json'
		header['User-Agent'] = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.11; rv:47.0) Gecko/20100101 Firefox/47.0'

		return header

	def __get_header_auth(self):
		auth_header = self.__get_header()
		auth_header['Authorization'] = 'Bearer %s' % self.__token

		token_renew_time = self.__auth_time + timedelta(seconds=self.TOKEN_DURATION_SECONDS)

		if datetime.now() > token_renew_time:
			token_max_time = self.__auth_time + timedelta(seconds=self.TOKEN_MAX_DURATION)
			if datetime.now() < token_max_time:
				self.__refresh_token()
			else:
				self.login()

			auth_header['Authorization'] = 'Bearer %s' % self.__token

		return auth_header

	def login(self):
		auth_url = self.API_BASE_URL + '/login'
		auth_data = dict()
		auth_data['apikey'] = self.api_key

		auth_resp = requests.post(url=auth_url, json=auth_data, headers=self.__get_header())

		if auth_resp.status_code == 200:
			auth_resp_data = json.loads(auth_resp.content)
			self.__token = auth_resp_data['token']
			self.__auth_time = datetime.now()
			self.is_authenticated = True
		else:
			raise AuthenticationFailedException('Authentication failed!')

	def __refresh_token(self):
		refresh_url = self.API_BASE_URL + "/refresh_token"
		header = self.__get_header()
		header['Authorization'] = 'Bearer %s' % self.__token

		refresh_resp = requests.get(url=refresh_url, headers=header)

		if refresh_resp.status_code == 200:
			# print "__refresh_token success"
			token_resp = json.loads(refresh_resp.content)
			self.__token = token_resp['token']
			self.__auth_time = datetime.now()
		else:
			print "__refresh_token failure"

	def search_series(self, name=None, imdb_id=None, zap2it_id=None):
		# print "search_series (name=%s, imdb_id=%s, zap2i_id=%s)" % (name, imdb_id, zap2it_id)

		search_url = self.API_BASE_URL + '/search/series'
		search = "%s?name=%s" % (search_url, name)

		search_resp = requests.get(url=search, headers=self.__get_header_auth())

		if search_resp.status_code == 200:
			# print "search_series success"
			return json.loads(search_resp.content)
		else:
			print "search_seres failure (%d) | search[%s] | name[%s]" % (search_resp.status_code, search, name)
			return
