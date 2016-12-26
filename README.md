yuri-button
====

百合だと思ったときに押すボタン on Raspberry Pi

## Demo

https://youtu.be/YVmoyazhSCM
https://youtu.be/N4OgzO5OwXw

## Install
```
$ sudo apt-get install libopencv-dev python-opencv python-smbus i2c-tools
$ sudo pip install requests requests_oauthlib
$ git clone https://github.com/dkishitani/yuri-button
$ cd yuri-button
$ wget https://raw.githubusercontent.com/nagadomi/lbpcascade_animeface/master/lbpcascade_animeface.xml
```
↓
settings.py を適当に書き換える
↓
```
$ ./yuri-button.py
```
