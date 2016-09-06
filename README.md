# wrun
Run Remote Windows Executables

## Installation

    pip install wrun
    
## Usage

To initialize a settings file

    wrun create <path>
    
To manage the windows service

    wrun --settings <path> [command]
    
Possible commands:

* install: create the windows service
* start: start the service
* stop: stop the service
* remove: remove the windows service

Base settings contained in settings file:

* SERVICE_NAME: Windows service name
* PLUGINS_PATH: absolute path for executables
* DAEMON_PORT: listening port for service
* LOG_CONFIG: log configuration
* HMAC_KEY: automatically generated at the wrun create, must be the same on client and server