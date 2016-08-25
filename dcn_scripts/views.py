#!/usr/bin/env python
'''
 Copyright 2016 wookieware.

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.


__author__ = "@netwookie"
__copyright__ = "Copyright 2016, wookieware."
__credits__ = ["Rick Kauffman"]
__license__ = "Apache2"
__version__ = "1.0.0"
__maintainer__ = "Rick Kauffman"
__email__ = "rick@rickkauffman.com"
__status__ = "Prototype"

Flask script that auto provisions HPE DCN
08232016 Initial release. This script will generate a new (tenant), a new domain and
add zones, subnets and default ACL rules for ingress and egress traffic. They default to open.



'''
from vspk import v3_2 as vsdk
import time
from flask import Flask, request, render_template, redirect, url_for, flash, session, send_file
from flask.ext.bootstrap import Bootstrap
from flask_sqlalchemy import SQLAlchemy
from models import db, Switches
from settings import APP_STATIC
import os
from flask import Flask, request, redirect, url_for
from werkzeug.utils import secure_filename
import ipaddress

UPLOAD_FOLDER = APP_STATIC
ALLOWED_EXTENSIONS = set(['csv'])

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

bootstrap = Bootstrap(app)
# Routes
# Main Menu
@app.route('/')
@app.route('/index')
def show_all():
    return render_template('main.html')

@app.route('/login', methods = ['GET', 'POST'])
def login():
    if request.method == 'POST':
        global nuage_user
        session['userx'] = request.form.get('user')
        session['passwd'] = request.form.get('passwd')
        session['org'] = request.form.get('org')
        ip = 'https://'+request.form.get('ipaddress')+':8443'
        session['ipaddress'] = ip
        # Configuring a connection to the VSD API
        nc = vsdk.NUVSDSession(username=session['userx'], password=session['passwd'], enterprise=session['org'], api_url=session['ipaddress'])

        # Actively connecting ot the VSD API
        try:
            nc.start()
        except:
            flash('Login Session Failed...Check Credentials')
            return render_template('main.html')
        # Root User
        nuage_user = nc.user

    return render_template('menu.html')

# Select record for editing
@app.route('/add_tenant', methods = ['GET', 'POST'])
def add_domain():
    if request.method == 'POST':
        pass
    return render_template('newtenant.html')

# Select record for editing
@app.route('/build_tenant', methods = ['GET', 'POST'])
def build_tenant():
    if request.method == 'POST':

        # Get form variable and make them session variable
        enterprise = request.form.get('enterprise')
        domain_new = request.form.get('domain')

        if (' ' in enterprise):
            flash('Spaces are not allowed in Tenant name')
            return render_template('newtenant.html')
        if (' ' in domain_new):
            flash('Spaces are not allowed in Domain name')
            return render_template('newtenant.html')

        # Copy from an existing 3-Tier domain
        # Rename to the new domain name

        domain = nuage_user.domains.get_first(filter='name == "Default Domain"')
        domain.fetch()


        job = vsdk.NUJob(command='EXPORT')

        # Creating export job for the Main VSPK Domain

        domain.create_child(job)

        # Printing the export result

        while True:
            job.fetch()
            if job.status == 'SUCCESS':
                # Copy domain details to new Enterprise
                enterprise = vsdk.NUEnterprise(name=enterprise)
                nuage_user.create_child(enterprise)
                job.result['parameters']['domain'][0]['modifyableAttributes']['name']['value'] = domain_new

                # Using the export copy of the domain details from above
                import_job = vsdk.NUJob(command='IMPORT', parameters=job.result)
                enterprise.create_child(import_job)
                break

            if job.status == 'FAILED':
                return render_template('fail_domain.html', var = enterprise)
            time.sleep(1)


        # Verify the import job has finished successfully
        while True:
            import_job.fetch()
            if import_job.status == 'SUCCESS':
                # get the new domain and provision it

                dom = nuage_user.domains.get_first(filter="name == '%s'" % domain_new)
                dom.fetch()
                # Create Zones

                global number_of_zones
                global number_of_subnets_per_zone
                global number_of_vports_per_subnet

                # Adjust these numbers as required for differnet use cases

                number_of_zones = 3 # Starts with zero
                number_of_subnets_per_zone = 1
                number_of_vports_per_subnet = 2

                is_template = dom.is_template()
                zone_class = vsdk.NUZoneTemplate if is_template else vsdk.NUZone
                subnet_class = vsdk.NUSubnetTemplate if is_template else vsdk.NUSubnet

                # generate a network and subnets
                network = ipaddress.ip_network(u'10.0.0.0/8')
                subnets = network.subnets(new_prefix=24)

                # create zones
                for i in range(0, number_of_zones):

                    zone = zone_class(name=enterprise.name + "Zone %d" % i)
                    dom.create_child(zone)
                    dom.add_child(zone)

                    #creates subnets
                    for j in range(0, number_of_subnets_per_zone):

                        # pull a subnet and get information about it
                        subnetwork = subnets.next()
                        ip = "%s" % subnetwork.network_address
                        gw = "%s" % subnetwork.hosts().next()
                        nm = "%s" % subnetwork.netmask

                        subnet = subnet_class(name="Subnet %d %d" % (i, j), address=ip, netmask=nm, gateway=gw)
                        zone.create_child(subnet)
                        zone.add_child(subnet)

                        # if the given domain is a template, we stop
                        if is_template:
                            break

                        # Otherwise we create the VPorts
                        for k in range(0, number_of_vports_per_subnet):

                            vport = vsdk.NUVPort(name="VPort %d-%d-%d" % (i, j, k), type="VM", address_spoofing="INHERITED", multicast="INHERITED")
                            subnet.create_child(vport)
                            subnet.add_child(vport)
                # Now add the default ACCESS Contol Lists for Ingress/egress

                # Creating the job to begin the policy changes
                job = vsdk.NUJob(command='BEGIN_POLICY_CHANGES')
                dom.create_child(job)
                # wait for the job to finish
                while True:
                    job.fetch()
                    if job.status == 'SUCCESS':
                        break
                    if job.status == 'FAILED':
                        return render_template('fail_acls.html', domain = domain)
                        break
                    time.sleep(1)# can be done with a while loop

                # Creating a new Ingress ACL
                ingressacl = vsdk.NUIngressACLTemplate(
                    name='Middle Ingress ACL',
                    priority_type='NONE', # Possible values: TOP, NONE, BOTTOM (domain only accepts NONE)
                    priority=100,
                    default_allow_non_ip=True,
                    default_allow_ip=True,
                    allow_l2_address_spoof=False,
                    active=True
                    )
                dom.create_child(ingressacl)

                # Creating a new egressgress ACL
                # TODO find out what the real element names are
                egressacl = vsdk.NUEgressACLTemplate(
                    name='Middle Egress ACL',
                    priority_type='NONE', # Possible values: TOP, NONE, BOTTOM (domain only accepts NONE)
                    priority=100,
                    default_allow_non_ip=True,
                    default_allow_ip=True,
                    allow_l2_address_spoof=False,
                    active=True
                    )
                dom.create_child(egressacl)

                # Creating a new Ingress ACL rule to allow database connectivity
                # from the Web-Tier Zone to the DB-Tier Zone
                from_network = dom.zones.get_first(filter='name == "WEB Zone2"')
                to_network = dom.zones.get_first(filter='name == "DB Zone2"')
                db_ingressacl_rule = vsdk.NUIngressACLEntryTemplate(
                    action='FORWARD',
                    description='Allow MySQL DB connections from Web Zone2',
                    ether_type='0x0800',
                    location_type='ZONE',
                    location_id=from_network.id,
                    network_type='ZONE',
                    network_id=to_network.id,
                    protocol='6',
                    source_port='*',
                    destination_port='3306',
                    dscp='*'
                    )
                ingressacl.create_child(db_ingressacl_rule)

                # Applying the changes to the domain
                job = vsdk.NUJob(command='APPLY_POLICY_CHANGES')
                dom.create_child(job)
                break

            if import_job.status == 'FAILED':
                return render_template('fail_domain.html', enterprise = enterprise)
                break
            time.sleep(1)


    return render_template('add_tenant_success.html')


@app.route('/logout')
def logout():
    session.pop('userx', None)
    session.pop('passwd', None)
    session.pop('org', None)
    session.pop('ipaddress', None)
    session.pop('enterprise', None)
    return redirect(url_for('index'))


@app.route('/help')
def help():
    return render_template('help.html')

@app.route('/about')
def about():
    return redirect('http://www.wookieware.com')


if __name__ == '__main__':
    #db.create_all()
    app.secret_key = 'SuperSecret'
    app.debug = True
    app.run(host='0.0.0.0')
