import logging
import subprocess
import os
import sys
import psutil
import threading
import random
from time import sleep
from kalliope.core.Utils import Utils
from kalliope.core.NeuronModule import NeuronModule, InvalidParameterException
from kalliope.core.Cortex import Cortex

logging.basicConfig()
logger = logging.getLogger("kalliope")

LOWER_VOLUME = 70
NAME = 0
LINK = 1

class Background_sound_player(NeuronModule):
    """
    Background sound player neuron
    Play the stream from a file or an url
    (for example: ./musics/zelda/fullOst.wav, or Radio Néo url like: http://stream.radioneo.org:8000/;stream/1)
    """
    def __init__(self, **kwargs):
        super(Background_sound_player, self).__init__(**kwargs)

        self.state = kwargs.get('state', None)                                  # "on" / "off"
        self.sounds = kwargs.get('sounds', None)                                # "[{'title1': 'link1'}, {'title2': 'link2'}, ...]"
        self.random_option = kwargs.get('random_option', "random-select-one")   # "random-order-play" / "random-select-one" / "no-random"
        self.loop_option = kwargs.get('loop_option', 'no-loop')                 # "loop" / "no-loop"
        self.mplayer_path = kwargs.get('mplayer_path', "/usr/bin/mplayer")      
        self.auto_stop_minutes = kwargs.get('auto_stop_minutes', None)
        self.volume = kwargs.get('volume', '100')

        self.currently_playing_sound = None
        self.mplayer_popen_obj = self.get_mplayer_popen_obj()

        # a dict of parameters the user ask to save in short term memory
        self.kalliope_memory = kwargs.get('kalliope_memory', None)
        # parameters loaded from the order can be save now
        Cortex.save_parameter_from_order_in_memory(self.kalliope_memory)

        # message dict that will be passed to the neuron template
        self.message = dict()

        # check if sent parameters are in good state
        if self._is_parameters_ok():
            if self.state == "off":
                self.stop_last_process()
                Cortex.save("current_playing_background_sound", "Aucun fond sonore lancé actuellement")
                Cortex.save("background_mplayer_popen", 'NIL')

            elif self.state == "lower_for_speaking":
                self.lower_sound_for_speaking()

            elif self.state == "higher_wonce_spoken":
                self.higher_sound_wonce_spoken()

            else:
                # we stop the last process if exist
                self.stop_last_process()

                # pick one sound randomly in all sounds entered
                if self.random_option == "random-select-one":
                    self.currently_playing_sound = [random.choice(self.sounds)]
                # play all sounds in random order
                elif self.random_option == "random-order-play":
                    random.shuffle(self.sounds)
                    self.currently_playing_sound = self.sounds
                # play all sounds the specified order
                else:
                    self.currently_playing_sound = self.sounds

                # then we can start a new process
                self.start_new_process(self.currently_playing_sound)

                # run auto stop thread
                if self.auto_stop_minutes:
                    thread_auto_stop = threading.Thread(target=self.wait_before_stop)
                    thread_auto_stop.start()

            # give the message dict to the neuron template
            self.say(self.message)

    def _is_playable_link(self, link):
        """
        Checks if the link is playable in mplayer.
        Not done yet.
        return: True if playable, False if it isn't
        """
        return True

    def _check_sounds(self, sounds):
        if (type(sounds) != type([]) or len(sounds) == 0):
            raise InvalidParameterException("[Background_sound_player] The sounds parameter is not set properly. Please use the representation specified in the documentation.")

        for sound in sounds:
            sound_name, sound_link = list(sound.items())[0]
            sound_name, sound_link = str(sound_name), str(sound_link)

            if sound_name == "":
                raise InvalidParameterException("[Background_sound_player] The name parameter is not set properly. Please set the name as specified in the documentation.")
            if sound_link == "":
                raise InvalidParameterException("[Background_sound_player] The link parameter is not set properly. Please set the link as specified in the documentation.")
            if self._is_playable_link(sound_link) is not True:
                raise InvalidParameterException("[Background_sound_player] The link " + sound_link + " is not a playble stream.")

        return True

    def wait_before_stop(self):
        logger.debug("[Background_sound_player] Wait %s minutes before checking if the thread is alive" % self.auto_stop_minutes)
        Utils.print_info("[Background_sound_player] Wait %s minutes before stopping the ambient sound" % self.auto_stop_minutes)
        sleep(self.auto_stop_minutes*60)  # *60 to convert received minutes into seconds
        logger.debug("[Background_sound_player] Time is over, Stop player")
        Utils.print_info("[Background_sound_player] Time is over, stopping the ambient sound")
        self.stop_last_process()

    def lower_sound_for_speaking(self):
        print('lowering sound')
        if self.mplayer_popen_obj is not None:
            self.mplayer_popen_obj.stdin.flush()
            self.mplayer_popen_obj.stdin.write('pausing_keep_force volume ' + str(LOWER_VOLUME) + ' 100\n')
            self.mplayer_popen_obj.stdin.flush()

    def higher_sound_wonce_spoken(self):
        print('highering sound')
        if self.mplayer_popen_obj is not None:
            self.mplayer_popen_obj.stdin.flush()
            self.mplayer_popen_obj.stdin.write('pausing_keep_force volume ' + self.volume + ' 100\n')
            self.mplayer_popen_obj.stdin.flush()

    def _is_parameters_ok(self):
        """
        Check that all given parameter are valid
        :return: True if all given parameter are ok
        """

        if self.state not in ["on", "off", "lower_for_speaking", "higher_wonce_spoken"]:
            raise InvalidParameterException("[Background_sound_player] State must be 'on' or 'off'")

        if self.state == "on":
            if self.sounds is None:
                raise InvalidParameterException("[Background_sound_player] You have to specify a sound parameter")
            elif type(self.sounds) != type([]):
                raise InvalidParameterException("[Background_sound_player] You have to specify the sound parameter as shown in the documentation.")
            if self._check_sounds(self.sounds) is not True:
                raise InvalidParameterException("[Background_sound_player] A sound parameter you specified in the list is not a valid playable link")
            if self.random_option not in ["random-select-one", "random-order-play", "no-random"]:
                raise ValueError("[Background_sound_player] random_option parameter must be \"random-select-one\" OR \"random-order-play\" OR \"no-random\" if specified")
            if self.loop_option not in ["loop", "no-loop"]:
                raise ValueError("[Background_sound_player] loop_option parameter must be \"loop\" OR \"no-loop\" if specified")

            try:
                int(self.volume)
            except ValueError:
                raise ValueError("[Background_sound_player] volume parameter must be \"-[Number between 0 and 100]\", for example: \"70\"")
                
            if not 0 <= int(self.volume) <= 100:
                raise ValueError("[Background_sound_player] volume parameter must be \"-[Number between 0 and 100]\", for example: \"70\"")

        # if wait auto_stop_minutes is set, must be an integer or string convertible to integer
        if self.auto_stop_minutes is not None:
            if not isinstance(self.auto_stop_minutes, int):
                try:
                    self.auto_stop_minutes = int(self.auto_stop_minutes)
                except ValueError:
                    raise InvalidParameterException("[Background_sound_player] auto_stop_minutes must be an integer")
            # check auto_stop_minutes is positive
            if self.auto_stop_minutes < 1:
                raise InvalidParameterException("[Background_sound_player] auto_stop_minutes must be set at least to 1 minute")
        return True

    @staticmethod
    def get_mplayer_popen_obj():
        ret_process = Cortex.get_from_key('background_mplayer_popen')
        if (ret_process == 'NIL'):
            ret_process = None

        return ret_process

    def stop_last_process(self):
        """
        stop the last mplayer process launched by this neuron
        :return:
        """

        if self.mplayer_popen_obj is not None:
            logger.debug("[Background_sound_player] loaded pid: %s" % self.mplayer_popen_obj.pid)
            self.mplayer_popen_obj.kill()
            logger.debug("[Background_sound_player] mplayer process with pid %s killed" % self.mplayer_popen_obj.pid)
            Cortex.save("current_playing_background_sound", "Aucun fond sonore lancé actuellement")
            Cortex.save("background_mplayer_popen", 'NIL')
        else:
            logger.debug("[Background_sound_player] Popen object is None. Process already stopped")

    def start_new_process(self, sound_arg):
        """
        Start mplayer process with the given sounds to play
        :param sound_arg:
        :type sound_arg: list of dicts [{name: link}, {name: link}, {name: link}]
        :return:
        """
        mplayer_exec_path = [self.mplayer_path]
        mplayer_options = ['-slave', '-quiet', '-af', 'volume=-10' '-volume', str(LOWER_VOLUME), '-loop']
        mplayer_options.append("0" if self.loop_option == "loop" else "1")

        mplayer_command = list()
        mplayer_command.extend(mplayer_exec_path)
        mplayer_command.extend(mplayer_options)

        for sound in sound_arg:
            for sound_name, sound_link in sound.items():
                mplayer_command.append(sound_link)

        logger.debug("[Background_sound_player] Mplayer cmd: %s" % str(mplayer_command))

        # give the current file name played to the neuron template
        self.message['sound_name'] = sound_name
        self.message["sound_link"] = sound_link

        # run mplayer in background inside a new process
        fnull = open(os.devnull, 'w')
        process = subprocess.Popen(mplayer_command, stdout=fnull, stderr=fnull, stdin=subprocess.PIPE, universal_newlines=True)
        pid = process.pid

        Cortex.save("current_playing_background_sound", sound_name)
        Cortex.save("background_mplayer_popen", process)
        logger.debug("[Background_sound_player] Mplayer started, pid: %s" % pid)
