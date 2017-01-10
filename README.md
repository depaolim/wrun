# wrun
Run Remote Windows Executables

## Installation

Install from pypi

    pip install wrun

### To use "Windows Service" on Windows

Install the last PyWin32 package
https://sourceforge.net/projects/pywin32/files/pywin32/

## Usage

You can create a Windows Service and use it via wrun.Proxy

#### Service Configuration

Create a configuration file with python syntax.
Example settings.py:

    EXECUTABLE_PATH = "C:\remote_activation"
    LOG_PATH = "C:\remote_activation\wrun.log"
    PORT = 3333
    
Mandatory settings:
 * EXECUTABLE_PATH: absolute path of the executables directory
 * LOG_PATH: absolute path of the daemon log file
 * PORT: daemon listening port
 
Optional settings:
 * HOST: host name or IP address (default: localhost)

#### Service Management

Create the Windows Service:

    wrun_service.py <service-name> <absolute-path-to-settings-file>

(wrun_service.py is a utility script installed alongside with wrun)

Start/Stop/Delete the service:

    sc start|stop|delete <service-name>

#### Client

Sample code:

    import wrun
    
    client = wrun.Proxy("localhost", 3333)
    result = client.run("sample.exe", "first-param", "second-param")
    print(result)
    # {"stdout": "OUTPUT", "returncode": 0}
    
 General form:
 
    import wrun
    
    client = wrun.Proxy(<server>, <port>)
    result = client.run(<executable_name>, <params>*)

 Some constraints:
 
 * server, port: connection parameters for daemon
 * executable_name: name of exe or script available in the EXECUTABLE_PATH of the daemon
 * params: various command line arguments passed to executable
 * result: dictionary with collected stdout and returncode
 
The client does not need PyWin32

## Tests
 
To run the test cases:

    git clone https://github.com/depaolim/wrun
    cd wrun
    python test.py
 
Some tests will be skipped if PyWin32 is not installed

## TODO

* Travis-CI
* hmac
* configurable logging (rotation, log-level, etc.)
