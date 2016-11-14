# DCN Manager

This is an application written in Flask. 

Installation:
git clone https://github.com/xod442/scriptsonly.git

Change directory to the dcn_scripts
look at the requirements.txt file and verify you have the necessary 
python libraries installed.


pip install -r requirements.txt (must have pip installed, if not:
sudo apt-get install python-pip

Start the application by issuing : python views.py from the project folder

The flask application will launch and can be access at:

http://hostname:5000 - app runs on port 5000.

Enter the login credentials, ip address and group id for your
Distributed Cloud Network controller. 

Initial Release - "Easy Button" 

Add a new tenant "Easy Button" then enter tenant name and domain. 

Package application in a docker container

Copy all files to a directory on a docker server:
run this command.... "docker build -t docker_id/image_name .   (mind the dot at the end.) 
This will pack this application in a docker image.

To launch docker container
docker run -p -d 5000:5000 docker_id/image_name

