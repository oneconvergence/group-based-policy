#!/usr/bin/perl

#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

use Data::Dumper;
local $Data::Dumper::Terse =1;
use JSON;
use LWP::UserAgent;

#Constants
my $httpclient = LWP::UserAgent->new;


my $get_admin_token_data =
{"auth" =>
    {"identity" =>
        {"methods" => ["password"],
         "password"=> {
         "user" => {
                "domain"=> {
                    "name"=> "Default"
                },
                "name"=> "",
                "password"=> ""
                }
            }
        },
     "scope" =>
         {"domain" => {
             "name" => "Default"
             }
         }
    }
};

my $get_user_token_data = 
{"auth" =>
    {"identity" =>
        {"methods" => ["password"],
         "password"=> {
         "user" => {
                "domain"=> {
                    "id"=> ""
                },
                "name"=> "", 
                "password"=> "" 
                }
            }
        },
        "scope" => {
            "project" => {
                "domain" => {
                    "id" => ""
                },
                "name" => ""
            }
        }
    }
};

#Global variables
my $admin_token_id;
my $user_token_id;
my $domain_id;
my $user_role;
my $cloud_admin_projname;
my $cloud_admin_username;
my $cloud_admin_password;
my $KEYSTONE_AUTH_URL;
my $REMOTE_VPN_ROLE_NAME;
my $SERVICE_PROJECT_ID;
my $username;
my $password;
my $user_id;
my $user_role_id;
my $url_get_admin_token = $KEYSTONE_AUTH_URL . "/v3/auth/tokens?nocatalog";
my $url_get_domain = $KEYSTONE_AUTH_URL . "/v3/projects/$SERVICE_PROJECT_ID";
my $url_user_authenticate = $KEYSTONE_AUTH_URL . "/v3/auth/tokens?nocatalog";
my $url_get_role_id = $KEYSTONE_AUTH_URL . "/v3/roles?name=$REMOTE_VPN_ROLE_NAME";
my $url_get_role_assignment = $KEYSTONE_AUTH_URL . "/v3/role_assignments?user.id=$user_id&role.id=$user_role_id";



sub read_auth_server_conf {
	# Get auth server conf from file
	my $AUTH_SERVER_CONF_FILE = "/usr/share/vyos/auth_server.conf";

	if (!open (AUTHFILE, $AUTH_SERVER_CONF_FILE)) {
		print "Could not open auth file : $AUTH_SERVER_CONF_FILE\n";
		exit 1;
	}
	$KEYSTONE_AUTH_URL = <AUTHFILE>;
	$cloud_admin_projname = <AUTHFILE>;
	$cloud_admin_username = <AUTHFILE>;
	$cloud_admin_password = <AUTHFILE>;
	$REMOTE_VPN_ROLE_NAME = <AUTHFILE>;
	$SERVICE_PROJECT_ID = <AUTHFILE>;

	chomp $KEYSTONE_AUTH_URL;
	chomp $cloud_admin_projname;
	chomp $cloud_admin_username;
	chomp $cloud_admin_password;
	chomp $REMOTE_VPN_ROLE_NAME;
	chomp $SERVICE_PROJECT_ID;


	close(AUTHFILE);
}


sub read_username_passwd {
	# Get username/password from file

	if ($ARG = shift @ARGV) {
		if (!open (UPFILE, "<$ARG")) {
			print "Could not open username/password file: $ARG\n";
	       		exit 1;
    		}
	} else {
    		print "No username/password file specified on command line\n";
    		exit 1;
	}

	$username = <UPFILE>;
	$password = <UPFILE>;

	if (!$username || !$password) {
    		print "Username/password not found in file: $ARG\n";
    		exit 1;
	}

	chomp $username;
	chomp $password;

	close (UPFILE);
}





sub get_cloud_admin_token {

    my $http_req = HTTP::Request->new(POST => $url_get_admin_token);
    $http_req->header('content-type' => 'application/json');
    $get_admin_token_data->{"auth"}{"identity"}{"password"}{"user"}{"name"} = $cloud_admin_username;
    $get_admin_token_data->{"auth"}{"identity"}{"password"}{"user"}{"password"} = $cloud_admin_password;
    $json_string = to_json($get_admin_token_data);
    $http_req->content($json_string);
    my $http_resp = $httpclient->request($http_req);
    if ($http_resp->is_success) {
        my $message = $http_resp->decoded_content;
        my $decoded_resp = decode_json($message);
        $admin_token_id = $http_resp->headers->{'x-subject-token'};
        print "Admin token id: ", $admin_token_id, "\n";
    }
    else {
        print "HTTP POST error code: ", $http_resp->code, "\n";
        print "HTTP POST error message: ", $http_resp->message, "\n";
        die "Getting cloud admin token failed \n";
    }
}

sub get_domain_id {
    my $http_req = HTTP::Request->new(GET => $url_get_domain);
    $http_req->header('content-type' => 'application/json');
    $http_req->header('x-auth-token' => $admin_token_id);

    my $http_resp = $httpclient->request($http_req);
    if ($http_resp->is_success) {
        my $message = $http_resp->decoded_content;
        my $decoded_resp = decode_json($message);
        $domain_id = $decoded_resp->{'project'}->{'domain_id'};
        $project_name = $decoded_resp->{'project'}->{'name'};
        print "Domain id: ", $domain_id, "\n";
        print "Project name: ", $project_name, "\n";
    }
    else {
        print "HTTP GET error code: ", $http_resp->code, "\n";
        print "HTTP GET error message: ", $http_resp->message, "\n";
        die "Getting domain id failed \n";
    }
}

sub get_role_id {
    my $http_req = HTTP::Request->new(GET => $url_get_role_id);
    $http_req->header('content-type' => 'application/json');
    $http_req->header('x-auth-token' => $admin_token_id);

    my $http_resp = $httpclient->request($http_req);
    if ($http_resp->is_success) {
        my $message = $http_resp->decoded_content;
        my $decoded_resp = decode_json($message);
        $user_role_id = $decoded_resp->{'roles'}[0]->{'id'};
        print "Role id: ", $user_role_id, "\n";
    }
    else {
        print "HTTP GET error code: ", $http_resp->code, "\n";
        print "HTTP GET error message: ", $http_resp->message, "\n";
        die "Getting role id failed \n";
    }
}




sub user_authenticate {
    my $http_req = HTTP::Request->new(POST => $url_user_authenticate);
    $http_req->header('content-type' => 'application/json');
    $get_user_token_data->{"auth"}{"identity"}{"password"}{"user"}{"domain"}{"id"} = $domain_id;
    $get_user_token_data->{"auth"}{"identity"}{"password"}{"user"}{"name"} = $username;
    $get_user_token_data->{"auth"}{"identity"}{"password"}{"user"}{"password"} = $password;
    $get_user_token_data->{"auth"}{"scope"}{"project"}{"domain"}{"id"} = $domain_id;
    $get_user_token_data->{"auth"}{"scope"}{"project"}{"name"} = $project_name;
    $json_string = to_json($get_user_token_data);
    $http_req->content($json_string);
    my $http_resp = $httpclient->request($http_req);

    if ($http_resp->is_success) {
        my $message = $http_resp->decoded_content;
        my $decoded_resp = decode_json($message);
        $user_token_id = $http_resp->headers->{'x-subject-token'};
	$user_id = $decoded_resp->{'token'}->{'user'}->{'id'};
        print "User token id: ", $user_token_id, "\n";
	print "User id: ", $user_id, "\n";
    }
    else {
        print "HTTP POST error code: ", $http_resp->code, "\n";
        print "HTTP POST error message: ", $http_resp->message, "\n";
        die "Getting user token failed \n";
    }
}

sub get_user_roles {
    $url_get_role_assignment = $KEYSTONE_AUTH_URL . "/v3/role_assignments?user.id=$user_id&role.id=$user_role_id";
    my $http_req = HTTP::Request->new(GET => $url_get_role_assignment);
    $http_req->header('content-type' => 'application/json');
    $http_req->header('x-auth-token' => $admin_token_id);

    my $http_resp = $httpclient->request($http_req);
    if ($http_resp->is_success) {
        my $message = $http_resp->decoded_content;
        my $decoded_resp = decode_json($message);
	my $user_roles = $decoded_resp->{'role_assignments'};
        my $len = @{$user_roles};
	if ($len) {
	   $user_role = $REMOTE_VPN_ROLE_NAME;
	} else {
	   $user_role = "";
	}
    }
    else {
        print "HTTP GET error code: ", $http_resp->code, "\n";
        print "HTTP GET error message: ", $http_resp->message, "\n";
        die "Getting user roles failed \n";
    }
}


read_auth_server_conf();
read_username_passwd();

$url_get_admin_token = $KEYSTONE_AUTH_URL . "/v3/auth/tokens?nocatalog";
$url_get_domain = $KEYSTONE_AUTH_URL . "/v3/projects/$SERVICE_PROJECT_ID";
$url_user_authenticate = $KEYSTONE_AUTH_URL . "/v3/auth/tokens?nocatalog";
$url_get_role_id = $KEYSTONE_AUTH_URL . "/v3/roles?name=$REMOTE_VPN_ROLE_NAME";
$url_get_role_assignment = $KEYSTONE_AUTH_URL . "/v3/role_assignments?user.id=$user_id&role.id=$user_role_id";

get_cloud_admin_token();
get_domain_id();
get_role_id();
user_authenticate();
get_user_roles();

if ($user_role eq $REMOTE_VPN_ROLE_NAME) {
    exit 0;
}
exit 1;
