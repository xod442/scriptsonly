#!/usr/bin/env python
'''
 2016 wookieware.

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.


__author__ = "@netwookie 2016, wookieware."
__credits__ = ["Rick Kauffman"]
__license__ = "Apache2"
__version__ = "1.0.0"
__maintainer__ = "Rick Kauffman"
__email__ = "rick@rickkauffman.com"
__status__ = "Prototype"

Flask script that auto provisions HPE DCN
08232016 Initial release. This script will generate a new (tenant), a new domain and
add zones, subnets and default ACL rules for ingress and egress traffic. They default to open.

#Needs to have a default enterprise with a L3 domain called "Default Domain"
TODO need to rewrite to use domain templates



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

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS

bootstrap = Bootstrap(app)

# Routes
@app.route('/index', methods=['POST', 'GET'])
@app.route('/', methods=['POST', 'GET'])
@app.route('/login', methods=['POST', 'GET'])
def login():
    error = None
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
        #return nuage_user
        return render_template('menu.html', error = error)
    return render_template('main.html')

# Select record for editing
@app.route('/return_to', methods = ['GET', 'POST'])
def return_to():
    return render_template('menu.html')

# Select record for editing
@app.route('/add_tenant', methods = ['GET', 'POST'])
def add_domain():
    if request.method == 'POST':
        pass
    return render_template('newtenant.html')

@app.route('/newacl', methods = ['GET', 'POST'])
def newinacl():
    if request.method == 'POST':
        domain = nuage_user.domains.get()
        count = 0
        domlist = []
        for dom in domain:
            domlist.append(dom.name)
            #print type(domain[count])
            count = count + 1
        return render_template('new_acl.html', domlist = domlist, count = count)

@app.route('/gathernewacldata', methods = ['POST'])
def gathernewinacldata():
    domain = request.form.get('domain')
    dom = nuage_user.domains.get_first(filter="name == '%s'" % domain)
    zonelist = []
    zones = dom.zones.get()
    for zon in zones:
        zonelist.append(zon.name)
    return render_template('gather_new_acl_data.html', domain = domain, zonelist = zonelist)

# Bulk import ingress/egress rules from csv file.
@app.route('/bulk', methods = ['GET', 'POST'])
def bulk():
    if request.method == 'POST':
        file = request.files['file']
        filename = secure_filename(file.filename)
        # check if the post request has the file part
        if 'file' not in request.files:
            flash('No file part')
            return render_template('chooser.html')
        # if user does not select file, browser also
        # submit a empty part without filename
        if file.filename == '':
            flash('No selected file')
            return render_template('chooser.html')
        #if file and allowed_file(file.filename):
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        vars = {}
        cr ='\n'
        filex = open(os.path.join(APP_STATIC, 'testdata.txt'), 'w')
        with open(os.path.join(APP_STATIC, filename)) as f:
            line = f.readline().strip('/t')
            while line:
                vars = str.split(line, ',')
                # assign the variables from the line of the csv file
                dom = vars[0]
                fromzone = vars[1]
                tozone = vars[2]
                direction = vars[3]
                action = vars[4]
                description = vars[5]
                ethertype = vars[6]
                protocol = vars[7]
                sourceport = vars[8]
                destinationport = vars[9]
                dscp = vars[10]
                #Get the domain
                if dom == 'eof':
                    break

                msg = 'In the loop'
                filex.write(line)
                filex.write(cr)

                domain = nuage_user.domains.get_first(filter="name == '%s'" % dom)
                domain.fetch()

                from_network = domain.zones.get_first(filter="name == '%s'" % fromzone)
                #print from_network.id
                to_network = domain.zones.get_first(filter="name == '%s'" % tozone)
                #print to_network.id

                if direction == 'Ingress':
                    for in_acl in domain.ingress_acl_templates.get():
                        db_ingressacl_rule = vsdk.NUIngressACLEntryTemplate(
                            action=action,
                            description=description,
                            ether_type=ethertype,
                            location_type='ZONE',
                            location_id=from_network.id,
                            network_type='ZONE',
                            network_id=to_network.id,
                            protocol=protocol,
                            source_port=sourceport,
                            destination_port=destinationport,
                            dscp=dscp
                            )
                        in_acl.create_child(db_ingressacl_rule)

                if direction == 'Egress':
                    for out_acl in domain.egress_acl_templates.get():
                        db_egressacl_rule = vsdk.NUEgressACLEntryTemplate(
                            action=action,
                            description=description,
                            ether_type=ethertype,
                            location_type='ZONE',
                            location_id=from_network.id,
                            network_type='ZONE',
                            network_id=to_network.id,
                            protocol=protocol,
                            source_port=sourceport,
                            destination_port=destinationport,
                            dscp=dscp
                            )
                        out_acl.create_child(db_egressacl_rule)
                line = f.readline().strip('/t')
                #time.sleep(5)

        f.close()
        filex.close()
        flash('Records processed')
        return render_template('bulk.html')
    return render_template('chooser.html')
#Needs to have a default enterprise with a L3 domain called "Default Domain"
@app.route('/buildaclrule', methods = ['POST'])
def buildaclrule():
    dom = request.form.get('domain')
    fromzone = request.form.get('fromzone')
    tozone = request.form.get('tozone')
    direction = request.form.get('direction')
    action = request.form.get('action')
    description  = request.form.get('description')
    ethertype= request.form.get('ethertype')
    protocol= request.form.get('protocol')
    sourceport = request.form.get('sourceport')
    destinationport = request.form.get('destinationport')
    dscp = request.form.get('dscp')
    '''
    return render_template('testvars.html',
    dom = dom,
    fromzone = fromzone,
    tozone = tozone,
    description = description,
    direction = direction,
    action = action,
    ethertype = ethertype,
    sourceport = sourceport,
    destinationport = destinationport,
    dscp = dscp,
    protocol = protocol
    )
    '''
    #Get the domain
    domain = nuage_user.domains.get_first(filter="name == '%s'" % dom)
    domain.fetch()

    from_network = domain.zones.get_first(filter="name == '%s'" % fromzone)
    #print from_network.id
    to_network = domain.zones.get_first(filter="name == '%s'" % tozone)
    #print to_network.id

    if direction == 'Ingress':
        for in_acl in domain.ingress_acl_templates.get():
            db_ingressacl_rule = vsdk.NUIngressACLEntryTemplate(
                action=action,
                description=description,
                ether_type=ethertype,
                location_type='ZONE',
                location_id=from_network.id,
                network_type='ZONE',
                network_id=to_network.id,
                protocol=protocol,
                source_port=sourceport,
                destination_port=destinationport,
                dscp=dscp
                )
            in_acl.create_child(db_ingressacl_rule)

    if direction == 'Egress':
        for out_acl in domain.egress_acl_templates.get():
            db_egressacl_rule = vsdk.NUEgressACLEntryTemplate(
                action=action,
                description=description,
                ether_type=ethertype,
                location_type='ZONE',
                location_id=from_network.id,
                network_type='ZONE',
                network_id=to_network.id,
                protocol=protocol,
                source_port=sourceport,
                destination_port=destinationport,
                dscp=dscp
                )
            out_acl.create_child(db_egressacl_rule)

    return render_template('add_acl_success.html')


# Select record for editing
@app.route('/build_tenant', methods = ['GET', 'POST'])
def build_tenant():
    if request.method == 'POST':

        # Get form variable and make them session variable
        enterprise = request.form.get('enterprise')
        domain_new = request.form.get('domain')
        number_of_zones = request.form.get('zones')
        number_of_subnets_per_zone = request.form.get('subs')
        number_of_vports_per_subnet = request.form.get('vports')
        # set variable as integers
        number_of_zones = int(number_of_zones)
        number_of_subnets_per_zone = int(number_of_subnets_per_zone)
        number_of_vports_per_subnet = int(number_of_vports_per_subnet)

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

                # Adjust these numbers as required for differnet use cases

                is_template = dom.is_template()
                zone_class = vsdk.NUZoneTemplate if is_template else vsdk.NUZone
                subnet_class = vsdk.NUSubnetTemplate if is_template else vsdk.NUSubnet

                # generate a network and subnets
                network = ipaddress.ip_network(u'10.0.0.0/8')
                subnets = network.subnets(new_prefix=24)

                # create zones
                for i in range(0, number_of_zones):

                    zone = zone_class(name=enterprise.name + "Zone%d" % i)
                    dom.create_child(zone)
                    dom.add_child(zone)

                    #creates subnets
                    for j in range(0, number_of_subnets_per_zone):

                        # pull a subnet and get information about it
                        subnetwork = subnets.next()
                        ip = "%s" % subnetwork.network_address
                        gw = "%s" % subnetwork.hosts().next()
                        nm = "%s" % subnetwork.netmask

                        subnet = subnet_class(name="Subnet%d%d" % (i, j), address=ip, netmask=nm, gateway=gw)
                        zone.create_child(subnet)
                        zone.add_child(subnet)

                        # if the given domain is a template, we stop
                        if is_template:
                            break

                        # Otherwise we create the VPorts
                        for k in range(0, number_of_vports_per_subnet):

                            vport = vsdk.NUVPort(name="VPort%d-%d-%d" % (i, j, k), type="VM", address_spoofing="INHERITED", multicast="INHERITED")
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
                from_network = dom.zones.get_first(filter='name == "WEBZone2"')
                to_network = dom.zones.get_first(filter='name == "DBZone2"')
                db_ingressacl_rule = vsdk.NUIngressACLEntryTemplate(
                    action='FORWARD',
                    description='Allow MySQL DB connections from WebZone2',
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

# Generate Ansible file
@app.route('/inventory', methods = ['GET', 'POST'])
def inventory():
    counter = 0
    cr ='\n'
    f = open(os.path.join(APP_STATIC, 'dcn_inventory.txt'), 'w')
    for cur_ent in nuage_user.enterprises.get():
        line = 'VMs inside Enterprise ' + cur_ent.name
        f.write(line)
        f.write(cr)
        for cur_vm in cur_ent.vms.get():
            line = '|- ' + cur_vm.name
            f.write(line)
            f.write(cr)

        line = 'Domains inside Enterprise ' + cur_ent.name
        f.write(line)
        f.write(cr)
        for cur_domain in cur_ent.domains.get():
            line = '|- Domain: ' + cur_domain.name
            f.write(line)
            f.write(cr)
            for cur_zone in cur_domain.zones.get():
                line = '    |- Zone: ' + cur_zone.name
                f.write(line)
                f.write(cr)
                for cur_subnet in cur_domain.subnets.get():
                    line = '        |- Subnets: ' + '' + cur_subnet.name + '' + cur_subnet.address + '' + cur_subnet.netmask
                    f.write(line)
                    f.write(cr)
            for cur_acl in cur_domain.ingress_acl_templates.get():
                line = '    |- Ingress ACL: ' + cur_acl.name
                f.write(line)
                f.write(cr)
                for cur_rule in cur_acl.ingress_acl_entry_templates.get():
                    line = '        |- Rule: ' + cur_rule.description
                    f.write(line)
                    f.write(cr)

            for cur_acl in cur_domain.egress_acl_templates.get():
                line = '    |- Egress ACL: ' + cur_acl.name
                f.write(line)
                f.write(cr)
                for cur_rule in cur_acl.egress_acl_entry_templates.get():
                    line = '        |- Rule: ' + cur_rule.description
                    f.write(line)
                    f.write(cr)
    f.close()
    f = open(os.path.join(APP_STATIC, 'dcn_inventory.txt'), 'r')
    file = f.read()
    f.close()
    flash('DCN inventory file has been created in /static/dcn_inventory.txt')
    return render_template('inventory.html', file = file)


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
