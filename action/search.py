#! /usr/bin/env python
import rospy
import actionlib

from riptide_msgs.msg import AttitudeCommand, LinearCommand
from nav_msgs.msg import Odometry
from std_msgs.msg import Float32, Int8
import riptide_autonomy.msg
from tf.transformations import euler_from_quaternion

import time
import math
import numpy as np
from actionTools import *

def angleDiff(a, b):
    return ((a-b+180) % 360)-180

class Search(object):
    drive_force = 20
    camera = 0

    def __init__(self):
        self.xPub = rospy.Publisher("command/x", LinearCommand, queue_size=1)
        self.yPub = rospy.Publisher("command/y", LinearCommand, queue_size=1)
        self.yawPub = rospy.Publisher("command/yaw", AttitudeCommand, queue_size=5)
        self.rollPub = rospy.Publisher("command/roll", AttitudeCommand, queue_size=5)

        self.cameraSub = rospy.Subscriber("command/camera", Int8, self.camCb)

        self._as = actionlib.SimpleActionServer(
            "search", riptide_autonomy.msg.SearchAction, execute_cb=self.execute_cb, auto_start=False)
        self._as.start()
        self.timer = rospy.Timer(rospy.Duration(0.05), lambda _: checkPreempted(self._as))

    def quatToEuler(self, quat):
        quat = [quat.x, quat.y, quat.z, quat.w]
        return np.array(euler_from_quaternion(quat)) * 180 / math.pi

    def camCb(self, msg):
        self.camera = msg.data
    
    def execute_cb(self, goal):
        rospy.loginfo("Start searching for %s", goal.obj)
        self.start_ang = goal.heading
        self.startTime = time.time()

        odomSub = rospy.Subscriber("odometry/filtered", Odometry, self.odomCb)
        waitAction(goal.obj, 5).wait_for_result()
        # Keep the yaw angle for aligning
        

        odomSub.unregister()
        y = self.quatToEuler(rospy.wait_for_message("odometry/filtered", Odometry).pose.pose.orientation)[2]
        self.yawPub.publish(y, AttitudeCommand.POSITION)
        self.xPub.publish(0, LinearCommand.FORCE)
        self.yPub.publish(0, LinearCommand.FORCE)
        self.rollPub.publish(0, AttitudeCommand.POSITION)

        self._as.set_succeeded()

    def odomCb(self, msg):
        euler = self.quatToEuler(msg.pose.pose.orientation)
        self.position = 20 * math.sin(math.pi / 3 * (time.time() - self.startTime))
        if self.camera == 0:
            self.yawPub.publish(angleDiff(self.position, -self.start_ang), AttitudeCommand.POSITION)
        else:
            self.rollPub.publish(angleDiff(self.position, 0), AttitudeCommand.POSITION)

        sy = math.sin(angleDiff(euler[2], self.start_ang) * math.pi / 180)
        cy = math.cos(angleDiff(euler[2], self.start_ang) * math.pi / 180)

        self.xPub.publish(self.drive_force * cy, LinearCommand.FORCE)
        self.yPub.publish(self.drive_force * sy, LinearCommand.FORCE)

if __name__ == '__main__':
    rospy.init_node('search')
    server = Search()
    rospy.spin()