#!/usr/bin/perl

#Usage: sudo perl op_commands.pl get_tunnel_state peer_ip tunnel-id


use lib "/opt/vyatta/share/perl5/";
use Vyatta::VPN::OPMode;
use Data::Dumper qw(Dumper);

sub get_ipsec_tunnel_count {
  my @args = @_;

  my $peer = $args[1];
  my @tunnel_hash = Vyatta::VPN::OPMode::get_tunnel_info_peer($peer);
  $DB::single = 1;
  my $count = $#tunnel_hash;
  $count = ($count + 1)/2;
  print "tunnels=$count";
  return $count;
}

sub get_ipsec_tunnel_idx {
  my @args = @_;

  my $peer = $args[1];
  my $lcidr = $args[2];
  my $pcidr = $args[3];

  my @tunnel_hash = Vyatta::VPN::OPMode::get_tunnel_info_peer($peer);
  my $count = ($#tunnel_hash + 1)/2;
  $DB::single = 1;
  for my $i (0..$count) {
    my $tun = $tunnel_hash[$i+1];
    my $lsnet = $tun->{_lsnet};
    my $rsnet = $tun->{_rsnet};
    if ($lcidr == $lsnet && $pcidr == $rsnet) {
      print "tunnel=$tun->{_tunnelnum} \n";
      return $tun->{_tunnelnum};
    }
  }
  print "tunnel=-1";
  return -1;
}

sub get_ipsec_tunnel_state {
  my @args = @_;


  my $peer = $args[1];
  my $tunnel = $args[2];

  my $tunidx = $tunnel + $tunnel - 1;
  my @tunnel_hash = Vyatta::VPN::OPMode::get_tunnel_info_peer($peer);
  
  my $state = $tunnel_hash[$tunidx]->{_state};

  print "state=$state\n";

  return $state
}


my $call=$ARGV[0];
$call->(@ARGV);
