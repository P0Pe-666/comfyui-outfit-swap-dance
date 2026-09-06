# -*- coding: utf-8 -*-
"""视频切分.bat 的 ASCII 入口：转发到中文名的切分脚本，规避 cmd 编码问题"""
import runpy
import sys

runpy.run_path(r"D:\Comfyui\切分脚本.py", run_name="__main__")
