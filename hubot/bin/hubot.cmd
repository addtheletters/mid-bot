@echo off

call npm install
SETLOCAL
SET PATH=node_modules\.bin;node_modules\hubot\node_modules\.bin;%PATH%

CALL "bin\set_environment.bat"

node_modules\.bin\hubot.cmd --name "mid-bot" %* 
