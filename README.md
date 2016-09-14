# wrun
Run Remote Windows Executables

## Installation

Install the last python 2.7 package (ex. Python 2.7.12)

Install the last PyWin32 package for python 2.7 (ex. PyWin32 220)

Clone the github repo (at the moment there is no proper setup)

    git clone https://github.com/depaolim/wrun
    
Install other dependencies:

    cd wrun
    pip install -r requirements.txt
    
## Usage

You can create a Windows Service and use it via wrun.Client

#### Service Configuration

Create a "ini" configuration file. Example wrun_service.ini:

    [DEFAULT]
    EXECUTABLE_PATH = C:\remote_activation
    PORT = 3333
    
 Mandatory settings are:
 * EXECUTABLE_PATH: absolute path of the directory where executables are stored
 * PORT: daemon listening port
 
 Optional settings are:
 * HMACKEY: if specified activates a secure client-server communication. Must be the same on the two sides

#### Service Management

Installation:

    cd wrun
    python win_service.py <service-name> <full-path-to-ini-file>
    
Start/Stop/Delete the service:

    sc start|stop|delete <service-name>

#### Client

Sample code:

    import wrun
    
    client = wrun.Client(REMOTE_HOST_NAME, "3331")
    result = client.run("sample.exe", "first-param", "second-param")
    print(result)
 
 Some constraints:
 
 * sample.exe must exit with exitcode 0. Otherwise an exception is raised
 * result is the collected standard output of sample.exe
 
The client does not need PyWin32, so you can use even a linux box as a client

## Tests
 
 To run the test cases:
 
    cd wrun
    python test.py
 
 Some tests will be skipped if PyWin32 is not installed

