# DS23 独立投影与来源审查

审查范围是 DS22 实际使用的原始深度、帧对应和空间投影合同。只读原代码与来源元数据；没有读取 GT raster、人工实例图、RGB 像素、深度像素，没有运行跟踪器、SDK playback、SAM3、补全或模型 API。真实端点像素复算由本轮主执行程序另行记录，不能用本文件的数学检查替代。

## 1. 实际生效入口

DS22 实际导入 `experiments/ds16_relative_depth_order/source.py`，不能只引用名称相近的 DS14。两份 source 文件当前逐字节一致；独立检查绑定两者。其 `RawDepth` 的 Feeding/FishSA 分支读取已存 RGB 网格深度和 native source index；L3/LW 分支现场从原始 native depth 投影。Geometry 的实际文件是 `E:/CAU/D-MOT/tools/depth_restoration/geometry.py`。FishSA 数据集内 `provenance/geometry.py` 和 `provenance/build_aligned_dataset.py` 也与当前生产模块逐字节一致。

|数据源|实际读取|实际生产或投影入口|
|---|---|---|
|Feeding 四段|`AlignedFeeding_v1/depth_rgb_640x360/*.npz` 的 `depth_mm/source_index`，同编号 native NPY|`tools/prelabel_feeding_20260924/build_aligned_feeding.py:63` 的 Geometry 与 `aligned_depth`，依赖原始 BAG 记录 profiles|
|FishSA 8400/2888|`AlignedDataset_v1` H5 的 `aligned/raw_depth_mm`、`aligned/raw_source_index`、`native/original_depth_mm`|`tools/depth_restoration/build_aligned_dataset.py:92`，原始 original depth 单独投影；不读取同容器的 v3 depth 或 instance_id|
|L3/LW|`AnnotationNewBags_20260919/{L3,LW}/manifest.json` 指向的 native NPY|实际 source.py:110–119，根据 `depth_usable` 现场投影；>5 ms 的来源输出缺测|

`source.py:66` 用 `source_color_index+1` 查 FishSA 的实际 RGB 帧，而 H5 存储 `frame_id=source_depth_index+1`。这两个编号域本来不同；实际入口检查 manifest 与 H5 frame_id，并按正确索引读取。RGB 第 1 帧原本无配对，保持缺测。不能把 H5 深度帧号直接当作 RGB 序列帧号。

## 2. 外参方向、畸变与深度定义

本地保存的官方 SDK 源码足以核对记录合同：

- `E:/CAU/D-MOT/logs/sdk_reference/RosbagWriter.cpp:338` 按 `k1,k2,k3,k4,k5,k6,p1,p2` 写 cameraDistortion，`:355` 明确对 depth 调用 `getExtrinsicTo(COLOR)` 写 R/t。
- `RosbagReader.cpp:229` 恢复 d2c，随后把 depth 到 color 的外参绑定回两个 stream。
- `ObTypes.h:453` 开始的枚举中数值 4 是 `OB_DISTORTION_BROWN_CONRADY_K6`；`:505` 起定义 K1–K6/P1/P2；`:519` 定义外参 translation 为毫米。
- `geometry.py:35` 将记录顺序转成 OpenCV 的 `[k1,k2,p1,p2,k3,k4,k5,k6]`；`:19–29` 在 native 深度网格做迭代 undistort 与反投影 roundtrip；`:26` 的行向量 `rays @ R.T` 等价于列向量 `R @ ray`。

实际计算是 `P_rgb = R @ (native_Z_mm * ray_depth) + t_mm`，再将 P_rgb 做 RGB 的 K6 前向畸变投影。保存的 aligned depth 是 `P_rgb.Z`；native depth 是 depth 相机 Z。两者不是径向距离，也不是同一坐标系的 Z，不能用“aligned depth 必须等于 native depth”来验收。

Feeding 的生产代码 `build_aligned_feeding.py:66–72` 已检查对应 640×576 depth/640×360 RGB SDK 模式、scale=1 mm，以及 SDK R/t 与记录 profiles 一致。本轮只核对已有 JSON 值，不再调用 SDK。不能将 SDK 另一分辨率（例如 1024×1024 depth）的主点直接替换录制的 640×576 profile；它们可能属于不同 crop/resolution。

四个 R 均按记录原值使用，非正交量在独立结果中如实列出。这不是未经实测校准就把 R 做 SVD 正交化的依据。记录矩阵的物理精度，以及水体/玻璃折射后的真实射线模型均为 UNKNOWN。

## 3. RGB 缩放与像素中心

原 RGB 是 1920×1080，共同网格 640×360。OpenCV 缩放对应 `u_small=(u_original+0.5)/3-0.5`、v 同式。

- Geometry 先按 1/3 缩 K；Feeding 生产代码 `build_aligned_feeding.py:74–75` 再把主点加 `(1/3-1)/2`。
- FishSA 生产 `build_aligned_dataset.py:45–47` 采用同样校正；其 `geometry_checks:226–234` 已检查完整投影再缩放与小网格投影等价。
- L3/LW 实际 source.py:71–72 同样加主点校正；保存 SAM3 polygon 在 source.py:55 使用完全相同的点坐标式再取整、填多边形。

因此，当前来源不存在“只缩 fx/fy/cx/cy 而遗漏半像素”的可证明错误。若将校正重复一次，或拿另一套 SDK 小网格 cx/cy 再额外减 1/3 像素，将改变原合同。不同方式的 polygon rasterization 与原二值 mask 的 resize 可能在边界上不完全相等；这属于掩码表达离散差异，不构成已证明的全局平移或鱼体空间配准错误。

`build_aligned_dataset.py:71–91` 的 rasterize 在 RGB 图像有效边界内取最近像素，最近 RGB-camera Z 优先；Z 完全相同时按最小 native index 定胜负。不插值、不补洞。薄鱼上的 missing/相邻遮挡污染可以由传感器视差、稀疏采样和 mask 包含背景产生，不能仅凭彩色图形就指认为缩放代码错位。

## 4. 三套时间配对合同

|来源|生产政策|有效性/限制|
|---|---|---|
|Feeding|`prelabel_feeding_20260924/prepare.py:21` 两路按时间排序后同序号 zip|每对断言绝对 delta≤5 ms；独立脚本另核对这些已存对也等于当前 RGB 的最近 depth，并回查原 timestamps|
|FishSA|`depth_restoration/prepare.py:20–24` 深度中心寻找最近 RGB；RGB 使用唯一|打包 `build_aligned_dataset.py:136–140` 再核对 nearest 与 delta≤5 ms；一个未配对 RGB 保留缺测|
|L3/LW|`prelabel_new_bags_20260919/prepare.py:29–31` RGB 中心寻找最近 depth|允许同一 depth 对应多个 RGB；>5 ms 标不可用。实际 source 分支保持此缺测，不从相邻帧填值|

以上只能检查配对合同，没有将深度像素时间平移至 RGB 曝光时刻。即使 ≤5 ms，快速运动仍可能产生边缘差异；它是误差源而非已证明的编号/时间配对 bug。实际 reused depth 数和 delta 分布由独立结果列出，不预设为 0。

## 5. 独立检查与证据边界

`projection_checks.py` 在固定 regular native 网格位置与固定合成 Z 上核对：真实 Geometry 的小网格投影、完整分辨率投影再按 pixel-center 缩放、独立 OpenCV projectPoints 三者。它另核对 source/producer 副本、四套完整来源 manifest 与原 timestamp 元数据、Feeding 已记录 SDK R/t/scale。输入仅 calibration 与 metadata，合成坐标不是原鱼体像素。真实结果记录在 `PROJECTION_CHECKS.json`，执行日志归主流程。

代码/源文件一致与数学等价通过，只能支持 **实现忠实于记录校准合同**。它不证明 mask 对应真实鱼体，也不证明 recorded calibration 在水中准确。未保存的 mirror 元信息也是来源边界：`extract_all_bag.py:94–122` 没有保存 `OBCameraParam.isMirrored`（官方 `ObTypes.h:532` 有该成员）；这是一项确定的元数据缺项，但没有证据把它升级为实际像素镜像错误，不能擅自翻转原图。

本次未找到可直接修复的缩放、畸变顺序、外参方向或 RGB/depth 帧编号错误。真实物理空间错位、mask 混入背景、视差遮挡和深度测量退化仍须用本轮固定端点观测分开描述；UNKNOWN 不写成“标定错误”或“配准正确”。没有按 GT、跟踪分数或残差最小值挑平移、转置、逆外参、深度帧偏移或其他变换。
