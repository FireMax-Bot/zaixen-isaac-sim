@echo off
cd /d D:\Robotics
call env_isaaclab\Scripts\activate.bat
set ROS_DISTRO=humble
set RMW_IMPLEMENTATION=rmw_fastrtps_cpp
rem set FASTRTPS_DEFAULT_PROFILES_FILE=D:\Robotics\fastdds_udp_only.xml
set ROS_DOMAIN_ID=0
set ROS_DISCOVERY_SERVER=127.0.0.1:11811
set PATH=%PATH%;D:\Robotics\env_isaaclab\Lib\site-packages\isaacsim\exts\isaacsim.ros2.core\humble\lib
isaacsim
pause
