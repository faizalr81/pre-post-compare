# pre-post-compare
This is the first readme.

Python use:
python3 junos_pre_post_compare.py \
  --pre pre_activity.txt \
  --post post_activity.txt \
  --output-prefix router01_comparison

Ansible use:
ansible-playbook compare_pre_post.yml
 or
ansible-playbook compare_pre_post.yml \
  -e "pre_file=/checks/router01_pre.txt" \
  -e "post_file=/checks/router01_post.txt" \
  -e "report_prefix=/checks/router01_report"

Result example:
==========================================================================================
JUNOS PRE/POST ACTIVITY COMPARISON
==========================================================================================

PASS    : 0
CHANGED : 0
REVIEW  : 0
FAIL    : 6

OVERALL RESULT: FAIL

SUMMARY
------------------------------------------------------------------------------------------
[FAIL] show chassis alarms | no-more
       POST contains a new potentially critical state

[FAIL] show chassis fpc | no-more
       POST contains a new potentially critical state

[FAIL] show bgp summary | no-more
       POST contains a new potentially critical state

[FAIL] show bfd session | no-more
       POST contains a new potentially critical state

[FAIL] show interfaces descriptions | no-more
       POST contains a new potentially critical state

[FAIL] show isis adjacency
       Adjacency present in PRE is missing from POST


==========================================================================================
COMMAND : show chassis alarms | no-more
STATUS  : FAIL
REASON  : New chassis alarm found in POST
------------------------------------------------------------------------------------------
--- PRE
+++ POST
@@ -1 +1,3 @@
-No alarms currently active
+1 alarms currently active
+Alarm time Class Description
+<TIMESTAMP> UTC Major FPC 1 Major Errors


==========================================================================================
COMMAND : show chassis fpc | no-more
STATUS  : FAIL
REASON  : FPC 1 changed from Online to Offline
------------------------------------------------------------------------------------------
--- PRE
+++ POST
@@ -1,3 +1,3 @@
 Temp CPU Utilisation (%) CPU Utilisation (%) Memory Utilisation (%)
 Slot State (C) Total Interrupt 1min 5min 15min DRAM (MB) Heap Buffer
-0 Online 41 4 0 5 4 4 4096 28 35
-1 Online 43 5 0 5 5 4 4096 30 36
+0 Online 42 5 0 5 5 4 4096 29 35
+1 Offline 43 0 0 0 0 0 4096 30 36


==========================================================================================
COMMAND : show bgp summary | no-more
STATUS  : FAIL
REASON  : Established BGP peer count decreased and one peer is Active
------------------------------------------------------------------------------------------
--- PRE
+++ POST
@@ -1,6 +1,6 @@
-Groups: 2 Peers: 3 Down peers: 0
+Groups: 2 Peers: 3 Down peers: 1
 Table Total Paths Active Paths Suppressed History Damp State Pending
-inet.0 1500 1450 0 0 0 0
+inet.0 1100 1050 0 0 0 0
 Peer AS InPkt OutPkt OutQ Flaps Last Up/Dwn State
-10.10.10.1 65001 10200 10150 0 0 <AGE> Establ
-10.10.10.2 65002 11200 11150 0 0 <AGE> Establ
-10.10.10.3 65003 9200 9150 0 0 <AGE> Establ
+10.10.10.1 65001 10500 10450 0 0 <AGE> Establ
+10.10.10.2 65002 11500 11450 0 0 <AGE> Establ
+10.10.10.3 65003 9250 9200 0 1 00:05 Active


==========================================================================================
COMMAND : show bfd session | no-more
STATUS  : FAIL
REASON  : BFD session changed from Up to Down
------------------------------------------------------------------------------------------
--- PRE
+++ POST
@@ -1,5 +1,5 @@
 Address State Interface Detection Time Transmit Interval Multiplier
 10.10.10.1 Up et-0/1/0.0 0.900 0.300 3
-10.10.10.2 Up et-0/1/1.0 0.900 0.300 3
+10.10.10.2 Down et-0/1/1.0 0.900 0.300 3
 2 sessions, 2 clients
-Cumulative transmit rate 6.6 pps, cumulative receive rate 6.6 pps
+Cumulative transmit rate 3.3 pps, cumulative receive rate 3.3 pps


==========================================================================================
COMMAND : show interfaces descriptions | no-more
STATUS  : FAIL
REASON  : Interface et-0/1/1 operational state changed from up to down
------------------------------------------------------------------------------------------
--- PRE
+++ POST
@@ -1,4 +1,4 @@
 Interface Admin Link Description
 et-0/1/0 up up Uplink-to-PE01
-et-0/1/1 up up Uplink-to-PE02
+et-0/1/1 up down Uplink-to-PE02
 xe-1/0/0 up up Customer-Link-01


==========================================================================================
COMMAND : show isis adjacency
STATUS  : FAIL
REASON  : IS-IS adjacency PE02 is missing from POST
------------------------------------------------------------------------------------------
--- PRE
+++ POST
@@ -1,3 +1,2 @@
 Interface System L State Hold (secs) SNPA
-et-0/1/0.0 PE01 2 Up 22
-et-0/1/1.0 PE02 2 Up 24
+et-0/1/0.0 PE01 2 Up 21


==========================================================================================
FINAL ASSESSMENT
==========================================================================================

Overall status : FAIL
Failed checks  : 6

Critical findings:
1. New major chassis alarm detected for FPC 1.
2. FPC 1 changed from Online to Offline.
3. BGP peer 10.10.10.3 changed from Established to Active



Ansible Result:
PLAY [Compare Junos PRE and POST activity results] ******************************

TASK [Check required local files] **********************************************
ok: [localhost] => (item=./pre_activity.txt)
ok: [localhost] => (item=./post_activity.txt)
ok: [localhost] => (item=./junos_pre_post_compare.py)

TASK [Stop when a required file is missing] ************************************
ok: [localhost] => (item=./pre_activity.txt)
ok: [localhost] => (item=./post_activity.txt)
ok: [localhost] => (item=./junos_pre_post_compare.py)

TASK [Build Python comparison command] *****************************************
ok: [localhost]

TASK [Run Junos PRE and POST comparison] ***************************************
ok: [localhost]

TASK [Display comparison output] ***********************************************
ok: [localhost] => {
    "comparison.stdout_lines": [
        "Text report : ./router01_comparison.txt",
        "CSV report  : ./router01_comparison.csv",
        "JSON report : ./router01_comparison.json",
        "",
        "FAIL     show chassis alarms | no-more: New chassis alarm found in POST",
        "FAIL     show chassis fpc | no-more: FPC 1 changed from Online to Offline",
        "FAIL     show bgp summary | no-more: BGP peer changed from Establ to Active",
        "FAIL     show bfd session | no-more: BFD session changed from Up to Down",
        "FAIL     show interfaces descriptions | no-more: Interface changed from up/up to up/down",
        "FAIL     show isis adjacency: IS-IS adjacency is missing from POST"
    ]
}

TASK [Display generated report locations] **************************************
ok: [localhost] => (item=./router01_comparison.txt) => {
    "msg": "Report generated: ./router01_comparison.txt"
}
ok: [localhost] => (item=./router01_comparison.csv) => {
    "msg": "Report generated: ./router01_comparison.csv"
}
ok: [localhost] => (item=./router01_comparison.json) => {
    "msg": "Report generated: ./router01_comparison.json"
}

TASK [Fail playbook when comparison detects a failure] *************************
fatal: FAILED! => {
    "changed": false,
    "msg": "PRE/POST validation failed. Review ./router01_comparison.txt and ./router01_comparison.csv."
}

PLAY RECAP *********************************************************************
localhost : ok=8 changed=0 unreachable=0 failed=1 skipped=1 rescued=0 ignored=0

