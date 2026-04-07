[app]
title = Cortana
package.name = cortana
package.domain = org.cortana

source.dir = .
source.include_exts = py,png,jpg,kv,atlas

version = 1.0.0

requirements = python3,kivy,requests,SpeechRecognition

orientation = portrait
fullscreen = 0

android.permissions = INTERNET, RECORD_AUDIO, MODIFY_AUDIO_SETTINGS
android.api = 33
android.minapi = 21
android.ndk = 25b
android.archs = arm64-v8a, armeabi-v7a

android.allow_backup = True
android.logcat_filters = *:S python:D

[buildozer]
log_level = 2
warn_on_root = 1
