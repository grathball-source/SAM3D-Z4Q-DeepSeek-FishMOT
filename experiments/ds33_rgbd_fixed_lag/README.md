# DS33运行入口

协议见PLAN.md。原Z4Q代码只读，入口controller.py使用真实矩阵边；sensor.py读取RGB/原始深度实录标定；flow.py计算真实像素对应及条件3D支持；evidence.py评估连续raw观测；lag.py只替换尚未首次发布的完整事务suffix；runner.py运行独立分支。

本机解释器：`E:/researchsoftware/anaconda3/envs/D-MOT/python.exe`。仅复用已安装OpenCV/NumPy/h5py/pycocotools/官方TrackEval依赖；不需要模型key。

运行检查须通过execute_unique.py，所有成功和失败诊断保留新时间戳日志，不能覆盖旧目录。freeze.py检查输入及科学依赖，orchestrate.py运行八段并封存访问记录，score.py只有全部预测封存且hash/语义合同有效后才能读参考。最后生成FINAL_REVIEW.md、PRIVATE_INVENTORY.json、公共发布manifest和远端核验。

复现实验前核实所有私有saved masks、原depth容器、RGB和实录calibration与SOURCE_MANIFEST/SENSOR_AUDIT/RGB_INPUT_PINS一致；不改旧DS14/DS18/DS32文件。正式run目录不可复用，应在新checkout或新明确输出路径复现。不要公开数据像素。
