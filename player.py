import threading
import datetime
__author__ = 'Jan'
import my_vlc
import time
import requests
import json
import logging
from my_vlc import State
logging.basicConfig(format='%(levelname)s: %(asctime)s %(name)s %(message)s',level=logging.DEBUG, filename="player.log")
#logging.basicConfig(format='%(levelname)s: %(asctime)s %(name)s %(message)s',level=logging.DEBUG)
class Player:
    def __init__(self):
        self.instance = my_vlc.get_default_instance()
        self.player = self.instance.media_player_new()
        self.now_playing = None
        self.next_song = None
        self.exit_player = False
    def play(self, e):
        logging.info('Player start')
        self.serve_forever(e)
        logging.info('Player exit')
        self.instance.release()
        self.player.release()
    def get_next_song(self):
        logging.info('Get next song start')
        payload = {"venue_id":12}
        url = None
        try:
            r = requests.post('http://api.songoroo.com/api/v1/device/getsong',json=payload)
            if r.status_code == 200:
                url = json.loads(r.text)['url']
            elif r.status_code == 400 and json.loads(r.json())['error_code']== 10:
                url = None
                logging.info('Device not streaming. Sleep ...')
                time.sleep(60)
            else:
                url = None
            self.next_song = url
        except requests.exceptions.ConnectionError as exc:
            logging.error(exc)
        except Exception as e:
            logging.error(e)
        logging.info('Get next song end. Url: %s', url)
    def serve_forever(self,e):
        while not self.exit_player:
            if self.player.is_playing() == 0 and self.player.get_media() != None:
                counter = 0
                logging.info('Song not loaded yet. Media state: %s. Waiting ....', self.player.get_media().get_state())
                state = self.player.get_media().get_state();
                if state == State.Opening:
                    while True:
                        if self.player.is_playing() == 1:
                            logging.info('Abort waiting. Song loaded.')
                            break
                        else:
                            counter+=0.1
                            if counter > 5:
                                logging.info('Abort waiting. Timeout.')
                                break
                            time.sleep(0.1)
                elif state == State.Error:
                    self.restart_playing()
                elif state == State.Ended or state == State.Stopped:
                    self.player.set_media(None)
            if self.player.is_playing() == 0 and self.player.get_media() == None and self.next_song == None:
                self.get_next_song()
            if self.player.is_playing() == 0 and self.player.get_media() == None and self.next_song != None:
                logging.info('Playing next song')
                self.now_playing_time = -1
                self.player = self.instance.media_player_new()
                self.set_now_playing()
                self.player.play()
            if self.player.is_playing() == 1 \
                and self.player.get_length() - self.player.get_time() < 15000 \
                    and self.next_song == None:
                logging.info('Less then 15000 msec to end of song. Getting next song.')
                self.get_next_song()
            if self.player.is_playing() == 1:
                if self.player.get_media() != None:
                    state = self.player.get_media().get_state()
                    if state == State.Error or state == State.Buffering or state == State.Ended or state == State.Stopped or state == State.Paused:
                        logging.info('Song playing. Media state: %s.', state)
                if self.now_playing_time == self.player.get_time():
                    ts=time.time()
                    logging.info('Song stucks. Waitint to recover.')
                    time.sleep(5)
                    if self.now_playing_time == self.player.get_time():
                        logging.info('Song not recovered. Tring restart song.')
                        self.restart_playing()
                    else:
                        logging.info('Song recovered. Continue playing.')
                self.now_playing_time = self.player.get_time()
            #logging.info("%s %s %s %s", self.player.is_playing(), self.player.get_media().get_state(), self.next_song,
            #             self.player.get_length() - self.player.get_time())
            e.set()
            time.sleep(1)
    def set_now_playing(self):
        self.now_playing = self.next_song
        self.next_song = None
        media = self.instance.media_new(self.now_playing)
        self.player.set_media(media)
    def restart_playing(self):
        logging.info('Restart actual song. Playing time : %s msec', self.now_playing_time)
        media = self.instance.media_new(self.now_playing)
        self.player.set_media(media)
        self.player.play()
        self.player.set_time(self.now_playing_time)
    def exit(self):
        self.exit_player = True
def wait_for_event(e, p):
    """Wait for the event to be set before doing anything"""
    logging.debug('wait_for_signal from player')
    event_is_set = True
    while event_is_set:
        e.clear()
        event_is_set = e.wait(120)
    logging.debug('Signal from player not received. Exit player. Event is: %s', event_is_set)
    p.exit()
e = threading.Event()
player = Player()
logging.info("start playing")
t1 = threading.Thread(name='block',
                      target=wait_for_event,
                      args=(e, player))
t2 = threading.Thread(name='player',
                      target=player.play,
                      args=(e, ))
t1.start()
t2.start()
t1.join()
t2.join()
logging.info("finish playing")
