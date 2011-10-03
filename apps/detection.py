#!/usr/bin/env python
import roscompat
import ecto
import ecto_geometry_msgs
import ecto_pcl
import ecto_ros
from ecto_opencv import highgui, cv_bp as opencv, calib, imgproc, features2d
from argparse import ArgumentParser
import os
import sys
import time
from ecto_object_recognition import tod_detection
from object_recognition.tod.feature_descriptor import FeatureDescriptor
from object_recognition import dbtools, models
from object_recognition.common.io.ros.source import KinectReader, BagReader
from object_recognition.common.filters.masker import Masker
from object_recognition.common.io.sink import Sink
from object_recognition.common.io.source import Source
from object_recognition.common.utils import json_helper
from object_recognition.tod.detector import TodDetector
import yaml

DEBUG = False
DISPLAY = True

PoseArrayPub = ecto_geometry_msgs.Publisher_PoseArray

########################################################################################################################

if __name__ == '__main__':
    plasm = ecto.Plasm()

    parser = ArgumentParser()

    # add arguments for the source and sink
    Source.add_arguments(parser)
    Sink.add_arguments(parser)

    parser.add_argument('--config_file' , '-c', help='Config file')

    # parse the arguments
    args = parser.parse_args()

    source = Source.parse_arguments(args)
    sink = Sink.parse_arguments(args)

    # TODO handle this properly...
    ecto_ros.init(sys.argv, "ecto_node")

    # define the input
    if args.config_file is None or not os.path.exists(args.config_file):
        raise 'option file does not exist'

    # read some parameters
    params = yaml.load(open(args.config_file))
    db_dict = params['db']
    db_url = db_dict['root']

    pipeline_params = []
    for key , value in params.iteritems():
        if key.startswith('pipeline'):
            pipeline_params.append(value)

    # define the input
    if 0:
        bag_reader = BagReader(plasm, dict(image=ecto_sensor_msgs.Bagger_Image(topic_name='image_mono'),
                           camera_info=ecto_sensor_msgs.Bagger_CameraInfo(topic_name='camera_info'),
                           point_cloud=ecto_sensor_msgs.Bagger_PointCloud2(topic_name='points'),
                           ), options.bag)

        # connect to the model computation
        point_cloud_to_mat = tod_detection.PointCloudToMat()
        plasm.connect(bag_reader['image'] >> tod_detector['image'],
                      bag_reader['point_cloud'] >> point_cloud_to_mat['point_cloud'],
                      point_cloud_to_mat['points'] >> tod_detector['points'])

    # define the different pipelines
    for pipeline_param in pipeline_params:
        if pipeline_param['type'] == 'TOD':
            detector = TodDetector(db_params=db_dict, feature_descriptor_params=pipeline_param['feature_descriptor'],
                                   guess_params=pipeline_param['guess'], search_params=pipeline_param['search'],
                                   object_ids=params['object_ids'], display=DISPLAY)

        # Connect the detector to the source
        for key in source.outputs.iterkeys():
            if key in detector.inputs.keys():
                plasm.connect(source[key] >> detector[key])

        # define the different outputs
        # TODO, they should all be connected to a merger first
        plasm.connect(detector['object_ids', 'Rs', 'Ts'] >> sink['object_ids', 'Rs', 'Ts'])

    # make sure that we also give the image_message, in case we want to publish a topic
    if 'image_message' in sink.inputs and 'image_message' in source.outputs:
        plasm.connect(source['image_message'] >> sink['image_message'])

    # Display the different poses
    if DISPLAY:
        pose_view = highgui.imshow(name="Pose")
        pose_drawer = calib.PosesDrawer()

        # draw the poses
        plasm.connect(source['image', 'K'] >> pose_drawer['image', 'K'],
                          detector['Rs', 'Ts'] >> pose_drawer['Rs', 'Ts'],
                          pose_drawer['output'] >> pose_view['image']
                          )

    # display DEBUG data if needed
    if DEBUG:
        print plasm.viz()
        ecto.view_plasm(plasm)

    # execute the pipeline
    sched = ecto.schedulers.Threadpool(plasm)
    sched.execute()
