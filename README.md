# Big data assignment 3

# Requirements
* Have Docker installed
* Download aisdk file and put it inside projects root directory
* Install neccesary dependencies for the project:
  * `pip install tenacity pymongo pandas matplotlib`

## Instructions for running the app
* Start mongodb replica set cluster by `docker-compose up -d`. Sometimes there can be an issue so incase, remove recently created cotainers and volumes
* Run the data import into mongodb `python Assignment_3.py`
* After the import is finished, run the histogram code: `python histogram.py`

## Troubleshooting connection issues:

If you have trouble connecting to the MongoDB replica set, make sure Docker is up and running. Make also sure that the host.docker.internal hostname can be resolved to the host machine's IP address.

### Modify Your Hosts File:
* Open your hosts file with administrative privileges:
  * Linux/macOS: /etc/hosts
  * Windows: C:\Windows\System32\Drivers\etc\hosts 
* Add the the following to the end of file: `127.0.0.1 host.docker.internal` and save

