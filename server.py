from flask import Flask, render_template, request, Response, jsonify
import requests
import tweepy
import os
import json
import random
import arrow
import time

app = Flask(__name__)

APP_KEY = os.environ.get('APP_KEY')
API_KEY = os.environ.get('TROVE_API_KEY')
TAG = os.environ.get('TAG')
CONSUMER_KEY = os.environ.get('CONSUMER_KEY')
CONSUMER_SECRET = os.environ.get('CONSUMER_SECRET')
ACCESS_TOKEN = os.environ.get('ACCESS_TOKEN')
ACCESS_TOKEN_SECRET = os.environ.get('ACCESS_TOKEN_SECRET')


def tweet(message, image=None):
    auth = tweepy.OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
    auth.set_access_token(ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
    api = tweepy.API(auth)
    if image:
        api.update_with_media(image, message)
    else:
        api.update_status(message)


def get_image(item):
    url = None
    image = None
    try:
        for identifier in item['identifier']:
            if identifier['linktype'] == 'thumbnail':
                url = identifier['value']
                break
        if url:
            thumbnail = 'thumbnail.jpg'
            request = requests.get(url, stream=True)
            if request.status_code == 200:
                with open(thumbnail, 'wb') as image:
                    for chunk in request:
                        image.write(chunk)
                image = 'thumbnail.jpg'
    except KeyError:
        pass
    return image

  
def truncate(message, length):
  if len(message) > length:
    message = '{}...'.format(message[:length])
  return message


def prepare_message(item, message_type):
    if message_type == 'new':
        message = 'New item tagged \'{}\'! {}: {}'
    elif message_type == 'random':
        message = 'Another Trove item tagged \'{}\'! {}: {}'
    details = None
    if item['zone'] == 'work':
        details = '{} ({})'.format(truncate(item['title'], 200), item['issued'])
    elif item['zone'] == 'article':
        date = arrow.get(item['date'], 'YYYY-MM-DD')
        details = '{}, \'{}\''.format(date.format('D MMM YYYY'), truncate(item['heading'], 200))
    if details:
        message = message.format(TAG, details, item['troveUrl'].replace('ndp/del', 'newspaper'))
    else:
        message = None
    return message


def save_max(zones):
    max = get_current_max(zones)
    if not os.path.exists('.data'):
        os.makedirs('.data')
    with open(os.path.join('.data', 'max.json'), 'wb') as max_file:
        json.dump({'max': max}, max_file)


def save_new_date(today):
    if not os.path.exists('.data'):
        os.makedirs('.data')
    with open(os.path.join('.data', 'since.json'), 'wb') as since_file:
        json.dump({'since': today}, since_file)


def get_last_max():
    try:
        with open(os.path.join('.data', 'max.json'), 'rb') as max_file:
            last = json.load(max_file)
            max = last['max']
    except IOError:
        max = 0
    return max


def get_last_date():
    try:
        with open(os.path.join('.data', 'since.json'), 'rb') as since_file:
            last = json.load(since_file)
            since = last['since']
    except IOError:
        since = '{}T00:00:00Z'.format(arrow.now().shift(years=-1).format('YYYY-MM-DD'))
    return since


def get_current_max(zones):
    max = 0
    for zone in zones:
        total = int(zone['records']['total'])
        if total > max:
            max = total
    return max


def authorised(request):
    if request.args.get('key') == APP_KEY:
        return True
    else:
        return False


@app.route('/')
def home():
    return 'hello, I\'m ready to tweet'


@app.route('/new/')
def tweet_new():
    status = 'nothing new to tweet'
    if authorised(request):
        date_since = get_last_date()
        print date_since
        # Tag dates only seemed to be searched by day -- so need to create a minimum of a day-long window
        date_to = '{}T00:00:00Z'.format(arrow.utcnow().shift(days=+1).format('YYYY-MM-DD'))
        url = 'http://api.trove.nla.gov.au/result/?q=taglastupdated:[{}+TO+{}]&l-publictag={}&zone=all&encoding=json&key={}'.format(date_since, date_to, TAG, API_KEY)
        print url
        response = requests.get(url)
        data = response.json()
        items = []
        zones = data['response']['zone']
        now = '{}T00:00:00Z'.format(arrow.utcnow().format('YYYY-MM-DD'))
        save_new_date(now)
        for zone in zones:
            if 'work' in zone['records']:
                for item in zone['records']['work']:
                    item['zone'] = 'work'
                    items.append(item)
            elif 'article' in zone['records']:
                for item in zone['records']['article']:
                    item['zone'] = 'article'
                    items.append(item)
        if items:
            item = random.choice(items)
            message = prepare_message(item, 'new')
            image = get_image(item)
            if message:
                print message
                tweet(message, image)
                status = 'ok, I tweeted something new'
    else:
        status = 'sorry, not authorised to tweet'
    return status


@app.route('/random/')
def tweet_random():
    status = 'nothing to tweet'
    if authorised(request):
        max = get_last_max()
        print max
        start = random.randrange(0, max + 1)
        url = 'http://api.trove.nla.gov.au/result/?q=+&l-publictag={}&zone=all&encoding=json&n=1&s={}&key={}'.format(TAG, start, API_KEY)
        print url
        response = requests.get(url)
        data = response.json()
        items = []
        zones = data['response']['zone']
        save_max(zones)
        for zone in zones:
            if 'work' in zone['records']:
                for item in zone['records']['work']:
                    item['zone'] = 'work'
                    items.append(item)
            elif 'article' in zone['records']:
                for item in zone['records']['article']:
                    item['zone'] = 'article'
                    items.append(item)
        if items:
            item = random.choice(items)
            message = prepare_message(item, 'random')
            image = get_image(item)
            if message:
                print message
                tweet(message, image)
                status = 'ok, I tweeted something random'
    else:
        status = 'sorry, not authorised to tweet'
    return status
