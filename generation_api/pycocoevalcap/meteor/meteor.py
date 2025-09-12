#!/usr/bin/env python

# Python wrapper for METEOR implementation, by Xinlei Chen
# Acknowledge Michael Denkowski for the generous discussion and help 

# Last modified : Wed 22 May 2019 08:10:00 PM EDT
# By Sabarish Sivanath
# To support Python 3

import os
import subprocess
import threading
import shutil

# Assumes meteor-1.5.jar is in the same directory as meteor.py.  Change as needed.
METEOR_JAR = 'meteor-1.5.jar'
JAR_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), METEOR_JAR)
JAR_EXISTS = os.path.isfile(JAR_PATH)

class Meteor:

    def __init__(self):
        self.meteor_cmd = ['java', '-jar', '-Xmx2G', METEOR_JAR, \
                '-', '-', '-stdio', '-l', 'en', '-norm']
        self.meteor_p = None
        # Used to guarantee thread safety
        self.lock = threading.Lock()

    def _spawn(self):
        if self.meteor_p is None:
            if not JAR_EXISTS:
                raise FileNotFoundError(f"METEOR jar not found at {JAR_PATH}")
            if shutil.which('java') is None:
                raise EnvironmentError('Java is not installed or not found in PATH')
            self.meteor_p = subprocess.Popen(
                self.meteor_cmd,
                cwd=os.path.dirname(os.path.abspath(__file__)),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                bufsize=1,
            )

    def compute_score(self, gts, res):
        self._spawn()
        assert(gts.keys() == res.keys())
        imgIds = gts.keys()
        scores = []

        eval_line = 'EVAL'
        self.lock.acquire()
        for i in imgIds:
            assert(len(res[i]) == 1)
            stat = self._stat(res[i][0], gts[i])
            eval_line += ' ||| {}'.format(stat)

        self.meteor_p.stdin.write('{}\n'.format(eval_line))
        for i in range(0,len(imgIds)):
            scores.append(float(self.meteor_p.stdout.readline().strip()))
        score = float(self.meteor_p.stdout.readline().strip())
        self.lock.release()

        return score, scores

    def method(self):
        return "METEOR"

    def _stat(self, hypothesis_str, reference_list):
        # SCORE ||| reference 1 words ||| reference n words ||| hypothesis words
        hypothesis_str = hypothesis_str.replace('|||','').replace('  ',' ')
        score_line = ' ||| '.join(('SCORE', ' ||| '.join(reference_list), hypothesis_str))
        self._spawn()
        self.meteor_p.stdin.write('{}\n'.format(score_line))
        return self.meteor_p.stdout.readline().strip()

    def _score(self, hypothesis_str, reference_list):
        self._spawn()
        self.lock.acquire()
        # SCORE ||| reference 1 words ||| reference n words ||| hypothesis words
        hypothesis_str = hypothesis_str.replace('|||','').replace('  ',' ')
        score_line = ' ||| '.join(('SCORE', ' ||| '.join(reference_list), hypothesis_str))
        self.meteor_p.stdin.write('{}\n'.format(score_line))
        stats = self.meteor_p.stdout.readline().strip()
        eval_line = 'EVAL ||| {}'.format(stats)
        # EVAL ||| stats 
        self.meteor_p.stdin.write('{}\n'.format(eval_line))
        score = float(self.meteor_p.stdout.readline().strip())
        # bug fix: there are two values returned by the jar file, one average, and one all, so do it twice
        # thanks for Andrej for pointing this out
        score = float(self.meteor_p.stdout.readline().strip())
        self.lock.release()
        return score
 
    def __del__(self):
        if getattr(self, 'lock', None) is not None:
            self.lock.acquire()
            if self.meteor_p is not None:
                self.meteor_p.stdin.close()
                self.meteor_p.kill()
                self.meteor_p.wait()
            self.lock.release()
