"""Read-only F766 depth lineage audit; no GT, restoration, network or inference."""
import gzip
import hashlib
import json
import os
from pathlib import Path
import socket
import sys
from unittest.mock import patch

sys.dont_write_bytecode = True
os.environ.update(CUDA_VISIBLE_DEVICES='', OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
import cv2
import numpy as np
from rosbags.rosbag1 import Reader
from rosbags.typesys import Stores, get_typestore, get_types_from_msg

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LAB = Path('E:/CAU/D-MOT')
DATA = LAB / 'data/AlignedFeeding_v1'
OLD = ROOT / 'experiments/ds3_depth_foreground_filter'
sys.path.insert(0, str(ROOT / 'experiments/ds1_depth_only'))
sys.path.insert(0, str(LAB / 'tools/jev_z4q_scene_v1_20260922/deps'))
from depth_measurement import decode, statistics, KERNEL
sys.path.insert(0, str(LAB / 'tools'))
from extract_all_bag import corrected_definition, decode_property, plain, property_names
sys.path.insert(0, str(LAB / 'tools/depth_restoration'))
from build_aligned_dataset import rasterize
from geometry import Geometry
cv2.setNumThreads(1)


def artifact(path):
    with path.open('rb') as stream:
        sha = hashlib.file_digest(stream, 'sha256').hexdigest()
    return dict(path=str(path), bytes=path.stat().st_size, sha256=sha)


def verify(item):
    actual = artifact(Path(item['path']))
    assert actual == item, (item, actual)


def summary(values):
    values = np.asarray(values, dtype='f8').ravel()
    good = values[np.isfinite(values) & (values > 0)]
    out = dict(n=int(values.size), finite_positive_n=int(good.size), zero_n=int((values == 0).sum()))
    if good.size:
        out.update(min_mm=float(good.min()), max_mm=float(good.max()), median_mm=float(np.median(good)),
                   mad_mm=float(np.median(np.abs(good-np.median(good)))),
                   q10_q25_q75_q90_mm=np.quantile(good, [.1,.25,.75,.9]).tolist(),
                   above_5000_mm_n=int((good > 5000).sum()), above_10000_mm_n=int((good > 10000).sum()))
    return out


def run():
    target = HERE / 'SOURCE_AUDIT.json'
    assert not target.exists(), 'refuse to overwrite audit'
    frame, token = 766, 'o012'
    manifest_path = DATA / 'manifest.jsonl'
    meta = next(row for row in map(json.loads, manifest_path.read_text(encoding='utf-8').splitlines()) if row['frame'] == frame)
    calibration_path = DATA / 'calibration.json'
    calibration = json.loads(calibration_path.read_text(encoding='utf-8'))
    scale = calibration['sdk']['sdk_playback_depth_scale_mm']
    native_path = DATA / meta['depth_native']
    aligned_path = DATA / meta['depth_aligned']
    native = np.load(native_path, allow_pickle=False)
    assert artifact(native_path)['sha256'] == meta['source_depth_sha256']
    with np.load(aligned_path, allow_pickle=False) as sensor:
        aligned, source_index = sensor['depth_mm'], sensor['source_index']
    assert native.shape == (576,640) and aligned.shape == source_index.shape == (360,640)
    pixels_path = OLD / 'private/feeding_000701_001060_pixels.jsonl.gz'
    seal_path = OLD / 'MEASUREMENTS_SEALED.json'
    seal = json.loads(seal_path.read_text(encoding='utf-8'))
    for item in seal['artifacts']:
        verify(item)
    freeze_path = OLD / 'FREEZE.json'
    freeze = json.loads(freeze_path.read_text(encoding='utf-8'))
    for item in freeze['code']:
        verify(item)
    verify(freeze['source_inventory'])
    source_inventory = json.loads(Path(freeze['source_inventory']['path']).read_text(encoding='utf-8'))
    source_row = next(row for row in source_inventory['feeding_000701_001060'] if row['frame'] == frame)
    assert Path(source_row['depth_path']) == aligned_path and source_row['depth_sha256'] == artifact(aligned_path)['sha256']
    measurements_path = OLD / 'feeding_000701_001060_measurements.jsonl.gz'
    with gzip.open(measurements_path,'rt',encoding='utf-8') as stream:
        measured_row = next(row for row in map(json.loads,stream) if row['frame'] == frame)
    assert measured_row['source_depth_sha256'] == source_row['depth_sha256']
    with gzip.open(pixels_path, 'rt', encoding='utf-8') as stream:
        row = next(row for row in map(json.loads, stream) if row['frame'] == frame)
    obj = row['objects'][token]
    own = decode(obj['source_mask'])
    occupancy = sum((decode(o['source_mask']).astype('u2') for o in row['objects'].values()), np.zeros(own.shape,'u2'))
    core = cv2.erode((own & (occupancy == 1)).astype('u1'), KERNEL).astype(bool)
    x0,y0,x1,y1 = obj['crop']
    selected = np.zeros(aligned.shape, bool)
    selected[y0:y1,x0:x1] = decode(obj['regions']['selected'])
    assert int(selected.sum()) == 57
    assert obj['crop'] == measured_row['objects'][token]['foreground']['crop']
    assert statistics(aligned,selected) == measured_row['objects'][token]['foreground']['selected']
    indices = source_index[selected]
    assert (indices >= 0).all() and (indices < native.size).all()
    native_values = native.ravel()[indices]
    ys,xs = np.nonzero(selected)
    native_y,native_x = np.divmod(indices, native.shape[1])

    geom = Geometry(calibration['recorded_profiles'],640,360)
    geom.kc[0,2] += (640/geom.color['width']-1)/2
    geom.kc[1,2] += (360/geom.color['height']-1)/2
    all_indices = np.flatnonzero(np.isfinite(native.ravel()) & (native.ravel() > 0))
    xyz = geom.rc.reshape(-1,3)[all_indices] * native.ravel()[all_indices,None] + geom.t
    reprojected, rebuilt_indices = rasterize(geom.project_xyz(xyz), xyz[:,2], all_indices)
    assert np.array_equal(aligned,reprojected) and np.array_equal(source_index,rebuilt_indices)
    selected_xyz = geom.rc.reshape(-1,3)[indices] * native_values[:,None] + geom.t
    assert np.array_equal(selected_xyz[:,2].astype('f4'), aligned[selected])
    projected_xy = geom.project_xyz(selected_xyz)
    selected_error = np.linalg.norm(projected_xy-np.column_stack([xs,ys]),axis=1)

    inventory_path = LAB / 'logs/bag_extract_20260924/source_inventory.json'
    source = json.loads(inventory_path.read_text(encoding='utf-8'))['bags'][0]
    bag = Path(source['bag'])
    assert bag.stat().st_size == source['size_bytes']
    devices, profiles, properties = [], [], []
    names = property_names()
    with Reader(bag) as reader:
        store = get_typestore(Stores.EMPTY)
        for conn in reader.connections:
            store.register(get_types_from_msg(corrected_definition(conn), conn.msgtype))
        metadata_connections = [c for c in reader.connections if c.msgtype != 'sensor_msgs/msg/Image']
        for conn,timestamp,raw in reader.messages(connections=metadata_connections):
            msg = store.deserialize_ros1(raw,conn.msgtype)
            assert bytes(store.serialize_ros1(msg,conn.msgtype)) == bytes(raw)
            if conn.msgtype == 'custom_msg/msg/OBDeviceInfo':
                device = plain(msg)
                devices.append({k:v for k,v in device.items() if k.lower() not in ('serialnumber','serial_number','serial','sn','uid')})
            elif conn.msgtype == 'custom_msg/msg/OBStreamProfileInfo':
                profiles.append(plain(msg))
            elif conn.msgtype == 'custom_msg/msg/OBProperty':
                item = decode_property(msg,names)
                properties.append({k:item[k] for k in ('propertyId','name','decoded_value') if k in item})
        depth_connections = [c for c in reader.connections if c.msgtype == 'sensor_msgs/msg/Image' and c.topic != '/cam/sensor_2/frameType_2']
        raw_meta = None
        target_ns = meta['depth_timestamp_us'] * 1000
        for conn,timestamp,raw in reader.messages(connections=depth_connections,
                                                 start=target_ns-10000000, stop=target_ns+10000000):
            msg = store.deserialize_ros1(raw,conn.msgtype)
            if msg.timestamp_usec != meta['depth_timestamp_us']:
                continue
            assert bytes(store.serialize_ros1(msg,conn.msgtype)) == bytes(raw)
            values = np.frombuffer(msg.data,dtype='>u2' if msg.is_bigendian else '<u2').reshape(msg.height,msg.step//2)[:,:msg.width]
            assert np.array_equal(values.astype('f4')*scale,native)
            raw_selected = values.ravel()[indices]
            assert np.array_equal(raw_selected.astype('f4')*scale,native_values)
            raw_meta = dict(encoding=msg.encoding,is_bigendian=msg.is_bigendian,width=msg.width,height=msg.height,step=msg.step,
                           pixel_bit_size=msg.pixel_bit_size,depth_units_recorded=msg.depth_units,number=msg.number,
                           timestamp_usec=msg.timestamp_usec,data_sha256=hashlib.sha256(msg.data).hexdigest(),
                           selected_raw_uint16=summary(raw_selected),raw_uint16_hex_min_max=[hex(int(raw_selected.min())),hex(int(raw_selected.max()))],
                           full_native_equals_raw_times_sdk_scale=True,selected_native_equals_raw_times_sdk_scale=True,
                           selected_unique_raw_value_n=int(np.unique(raw_selected).size))
            break
    assert raw_meta is not None
    depth_properties = [p for p in properties if any(s in p['name'] for s in ('DEPTH','TOF','DISTANCE','FILTER','PRESET'))]
    base_property_ids = {p['propertyId']-65535 if p['propertyId'] >= 65535 else p['propertyId'] for p in properties}
    result = dict(status='READONLY_SOURCE_LINEAGE_VERIFIED_PHYSICAL_DEPTH_UNKNOWN',frame=frame,token=token,
        boundary=dict(npz_keys_read=['depth_mm','source_index'],annotation_pixels_read=0,v3_reads=0,sealed_test_reads=0,
                      old_model_response_reads=0,network_connections=0,server_jobs=0,training=0),
        lineage=dict(source_bag=source['bag'],recorded_bag_sha256=source['sha256'],source_bag_current_size_matches_inventory=True,
                     native=artifact(native_path),aligned=artifact(aligned_path),calibration=artifact(calibration_path),
                     manifest=artifact(manifest_path),sealed_ds3_pixels=artifact(pixels_path),sdk_depth_scale_mm=scale,
                     sdk_scale_verification_record=artifact(LAB/'logs/bag_extract_20260924/sdk_depth_scale.json'),
                     extraction_code=artifact(LAB/'FishSA-main/data_collect/3_run_Bag2HDF5.py')),
        old_ds3_binding=dict(measurement_seal=artifact(seal_path),freeze=artifact(freeze_path),
                             sealed_artifacts_verified=len(seal['artifacts']),frozen_code_artifacts_verified=len(freeze['code']),
                             source_inventory_verified=True,source_depth_sha256_matches=True,selected_stats_match_sealed_ds3=True),
        device_records=devices,recorded_stream_profiles=profiles,recorded_depth_related_properties=depth_properties,
        recorded_property_inventory=[dict(propertyId=p['propertyId'],name=p['name']) for p in properties],
        physical_range_evidence=dict(status='UNKNOWN',recorded_property_count=len(properties),
                                     min_depth_property_22_recorded=22 in base_property_ids,
                                     max_depth_property_23_recorded=23 in base_property_ids,
                                     note='No certified usable depth range or water calibration is supplied by these source records. '
                                          'The pre-existing dataset >5000 mm flag is an anomaly-candidate policy, not a sensor limit. '
                                          'Do not apply a bit mask, divide the component, or infer a multipath/noise cause from its integer values.'),
        raw_message=raw_meta,whole_raw_aligned=statistics(aligned,own),core_raw_aligned=statistics(aligned,core),
        selected_aligned=summary(aligned[selected]),selected_native=summary(native_values),
        source_index=dict(selected_n=int(indices.size),unique_native_sources=int(np.unique(indices).size),
                          native_bbox_xyxy=[int(native_x.min()),int(native_y.min()),int(native_x.max()+1),int(native_y.max()+1)]),
        projection=dict(full_depth_bit_exact=True,full_source_index_exact=True,selected_camera_z_bit_exact=True,
                        selected_projection_rounding_max_error_px=float(selected_error.max()),
                        selected_camera_z_minus_native_mm=dict(min=float((selected_xyz[:,2]-native_values).min()),
                            median=float(np.median(selected_xyz[:,2]-native_values)),max=float((selected_xyz[:,2]-native_values).max()))),
        frame_native=summary(native),frame_aligned=summary(aligned),
        conclusions=['The 57-point component already exists in the original mono16 BAG payload and native NPY.',
                     'Its aligned values and all source indices exactly reproduce the recorded calibration and nearest-Z rasterizer.',
                     'No evidence here attributes the component to restoration, interpolation, byte order or aligned-source substitution.',
                     'Finite positive and compact stable support do not establish a reliable physical distance.',
                     'Recorded device properties must be distinguished from certified physical range and water calibration.',
                     'Hardware failure mode and actual physical distance remain UNKNOWN; no bit correction is justified.'])
    with target.open('x',encoding='utf-8') as stream:
        json.dump(result,stream,ensure_ascii=False,indent=2,allow_nan=False)
        stream.write('\n')
    print(json.dumps({k:result[k] for k in ('status','raw_message','selected_aligned','selected_native','source_index','projection','recorded_depth_related_properties')},ensure_ascii=False,indent=2))


if __name__ == '__main__':
    original_open = Path.open
    original_key = np.lib.npyio.NpzFile.__getitem__
    def guarded_open(path,*args,**kwargs):
        normalized = str(path).replace('\\','/').lower()
        assert not any(s in normalized for s in ('labels_640x360','labels_source','labels_original','restoration/v3','sealed_test','response')),path
        return original_open(path,*args,**kwargs)
    def guarded_key(sensor,key):
        assert key in ('depth_mm','source_index'),key
        return original_key(sensor,key)
    with patch.object(Path,'open',guarded_open), patch.object(np.lib.npyio.NpzFile,'__getitem__',guarded_key), \
         patch.object(socket.socket,'connect',side_effect=AssertionError('no network')):
        run()
