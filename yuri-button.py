#!/usr/bin/env python
# -*- coding: utf-8 -*-

import requests
import settings
import smbus
import RPi.GPIO as GPIO
import time
import cv2
import base64
from requests_oauthlib import OAuth1Session


def lcd_cleanup(bus):
    lcd_byte(0x01, 0, bus)


def lcd_string(message, line_num, bus):
    if len(message) > 16:
        output = message[:settings.LCD_WIDTH]
    else:
        output = message.ljust(settings.LCD_WIDTH, ' ')

    if line_num == 1:
        lcd_byte(0x80, 0, bus)
    elif line_num == 2:
        lcd_byte(0xc0, 0, bus)
    else:
        return

    for i in range(settings.LCD_WIDTH):
        lcd_byte(ord(output[i]), 1, bus)
    

def lcd_init():
    bus = smbus.SMBus(settings.I2C_BUS)
    lcd_byte(0x33, 0, bus)
    lcd_byte(0x32, 0, bus)
    lcd_byte(0x06, 0, bus)
    lcd_byte(0x0c, 0, bus)
    lcd_byte(0x28, 0, bus)
    lcd_byte(0x01, 0, bus)
    time.sleep(0.0005)
    return bus


def lcd_byte(bits, mode, bus):
    bits_high = mode | (bits & 0xf0) | 0x08
    bits_low = mode | ((bits<<4) & 0xf0) | 0x08

    bus.write_byte(settings.I2C_ADDR, bits_high)
    lcd_toggle_enable(bits_high, bus)
    bus.write_byte(settings.I2C_ADDR, bits_low)
    lcd_toggle_enable(bits_low, bus)


def lcd_toggle_enable(bits, bus):
    time.sleep(0.0005)
    bus.write_byte(settings.I2C_ADDR, (bits | 0b00000100))
    time.sleep(0.0005)
    bus.write_byte(settings.I2C_ADDR, (bits | ~0b00000100))
    time.sleep(0.0005)


def nasne_title():
    try:
        r = requests.get('http://{}:64210/status/dtcpipClientListGet'.format(settings.NASNE_IP))
    except:
        return u''
    if r.status_code != 200:
        return u''

    data = r.json()
    if not 'client' in data:
        return u''

    if 'content' in data['client'][0]:
        return nasne_record(data['client'][0]['content']['id'])

    return nasne_onair()


def nasne_record(rec_id):
    r = requests.get('http://{}:64220/recorded/titleListGet'.format(settings.NASNE_IP),
                     params={
                         'searchCriteria': 0,
                         'filter': 0,
                         'startingIndex': 0,
                         'requestedCount': 0,
                         'sortCriteria': 0,
                         'id': rec_id,
                     })
    if r.status_code != 200:
        return u''
        
    data = r.json()
    if not 'item' in data:
        return u''
            
    return unicode(data['item'][0]['title'])


def nasne_onair():
    r1 = requests.get('http://{}:64210/status/boxStatusListGet'.format(settings.NASNE_IP))
    if r1.status_code != 200:
        return u''

    data1 = r1.json()
    if not 'tuningStatus' in data1:
        return u''

    r2 = requests.get('http://{}:64210/status/channelInfoGet2'.format(settings.NASNE_IP),
                      params={
                          'networkId': data1['tuningStatus']['networkId'],
                          'transportStreamId': data1['tuningStatus']['transportStreamId'],
                          'serviceId': data1['tuningStatus']['serviceId']
                      })
    if r2.status_code != 200:
        return u''

    data2 = r2.json()
    if not 'channel' in data2:
        return u''

    return unicode(data2['channel']['title'])


def twitter_media_upload(img, session):
    filename = '__upload.png'
    cv2.imwrite(filename, img)
    try:
        req = session.post('https://upload.twitter.com/1.1/media/upload.json',
                           files={'media': open(filename, 'rb')})
        return req.json().get(u'media_id_string', u'')
    except:
        return ''


def twitter_post(message, img_raw, img_detect):
    if len(message) > 140:
        print 'message is too long! -> %s' % message
        return False

    twitter_session = OAuth1Session(settings.TWITTER_CONSUMER_KEY,
                                    settings.TWITTER_CONSUMER_SECRET,
                                    settings.TWITTER_ACCESS_TOKEN,
                                    settings.TWITTER_ACCESS_SECRET)
    raw_id = twitter_media_upload(img_raw, twitter_session)
    detected_id = twitter_media_upload(img_detect, twitter_session)
    if not raw_id and not detected_id:
        print 'img upload failed.'
        return False

    req = twitter_session.post('https://api.twitter.com/1.1/statuses/update.json',
                               params={
                                   'status': message,
                                   'media_ids': u','.join([raw_id, detected_id])
                               })

    if req.status_code == 200:
        return True

    print "Error code: %d" % req.status_code
    return False


def init():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(settings.GPIO_PIN, GPIO.IN)
    lcd_bus = lcd_init()
    lcd_banner(lcd_bus)

    return lcd_bus


def cleanup(bus):
    lcd_cleanup(bus)
    GPIO.cleanup()


def button_loop(bus):
    while True:
        if GPIO.input(settings.GPIO_PIN):
            pressed(bus)
        time.sleep(0.1)

def detect(img, cascade_file='./lbpcascade_animeface.xml'):
    cascade = cv2.CascadeClassifier(cascade_file)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)

    faces = cascade.detectMultiScale(gray,
                                     scaleFactor = 1.1,
                                     minNeighbors = 5,
                                     minSize = (24, 24))

    detected_img = img.copy()
    for (x, y, w, h) in faces:
        cv2.rectangle(detected_img, (x,y), (x+w, y+h), (0, 0, 255), 2)

    return len(faces), detected_img


def capture_and_detect():
    video = cv2.VideoCapture(0)

    result, img = video.read()
    if not result:
        print 'can\'t read camera!'
        return None, None, 0

    video.release()
    num, detected_img = detect(img)

    return img, detected_img, num

def pressed(bus):
    print 'pressed!'
    lcd_cleanup(bus)
    lcd_string('pressed!', 1, bus)
    raw_img, detected_img, num = capture_and_detect()
    if raw_img is None:
        return

    print 'detected faces: %d' % num

    lcd_string('post->twitter...', 1, bus)

    if num >= 3:
        message = u'3人からがカップリング\U0001f631\U0001f631\U0001f631\U0001f631\U0001f631\U0001f631'
    else:
        message = u'百合をありがとう…ありがとう…\U0001f62d\U0001f62d\U0001f62d\U0001f62d\U0001f62d\U0001f62d'

    title = nasne_title()
    print 'nasne title: ' + title
    if title:
        message += u' => ' + title

    if twitter_post(message, raw_img, detected_img):
        lcd_string('      ->success!', 2, bus)
    else:
        lcd_string('      ->failed!', 2, bus)

    time.sleep(3)
    lcd_banner(bus)


def lcd_banner(bus):
    lcd_string('YURI Button', 1, bus)
    lcd_string('YURI Button'.rjust(settings.LCD_WIDTH, ' '), 2, bus)


def main():
    lcd_bus = init()
    try:
        button_loop(lcd_bus)
    finally:
        cleanup(lcd_bus)


if __name__ == '__main__':
    main()
