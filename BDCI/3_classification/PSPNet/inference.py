from __future__ import print_function
import os
import sys
import time
from PIL import Image
import tensorflow as tf
import numpy as np

from pspnet_model import PSPNet
from tools import decode_labels


class Tools(object):

    @staticmethod
    def new_dir(path):
        if not os.path.exists(path):
            os.makedirs(path)
        return path

    @staticmethod
    def print_info(info):
        print("{} {}".format(time.strftime("%H:%M:%S", time.localtime()), info))
        pass

    pass


class Runner(object):

    def __init__(self, is_flip=False, num_classes=5,
                 log_dir="./model_bdci_5", model_name="model.ckpt", save_dir="./output_bdci_5"):

        self.save_dir = Tools.new_dir(save_dir)
        self.log_dir = Tools.new_dir(log_dir)
        self.model_name = model_name
        self.checkpoint_path = os.path.join(self.log_dir, self.model_name)

        self.config = tf.ConfigProto()
        self.config.gpu_options.allow_growth = True

        self.img_mean = np.array((103.939, 116.779, 123.68), dtype=np.float32)
        self.input_size = [1024, 2048]
        self.crop_size = [720, 720]
        self.num_classes = num_classes

        self.is_flip = is_flip
        pass

    # 初始化网络：输入图片数据，输出预测结果
    def _init_net(self, img):
        img_shape = tf.shape(img)
        h, w = (tf.maximum(self.crop_size[0], img_shape[0]), tf.maximum(self.crop_size[1], img_shape[1]))
        img = self._pre_process(img, h, w)

        # Create network.
        net = PSPNet({'data': img}, is_training=False, num_classes=self.num_classes)
        with tf.variable_scope('', reuse=True):
            flipped_img = tf.image.flip_left_right(tf.squeeze(img))
            flipped_img = tf.expand_dims(flipped_img, dim=0)
            net2 = PSPNet({'data': flipped_img}, is_training=False, num_classes=self.num_classes)

        raw_output = net.layers["conv6"]
        if self.is_flip:
            flipped_output = tf.image.flip_left_right(tf.squeeze(net2.layers['conv6']))
            flipped_output = tf.expand_dims(flipped_output, dim=0)
            raw_output = tf.add_n([raw_output, flipped_output])

        # Predictions.
        raw_output_up = tf.image.resize_bilinear(raw_output, size=[h, w], align_corners=True)
        raw_output_up = tf.image.crop_to_bounding_box(raw_output_up, 0, 0, img_shape[0], img_shape[1])
        raw_output_up = tf.argmax(raw_output_up, axis=3)
        predictions = tf.expand_dims(raw_output_up, dim=3)
        return predictions

    # 读取图片数据
    @staticmethod
    def _load_img(img_path):
        if os.path.isfile(img_path):
            Tools.print_info('successful load img: {0}'.format(img_path))
        else:
            Tools.print_info('not found file: {0}'.format(img_path))
            sys.exit(0)
            pass
        filename = os.path.split(img_path)[-1]
        ext = os.path.splitext(filename)[-1]
        if ext.lower() == '.png':
            img = tf.image.decode_png(tf.read_file(img_path), channels=3)
        elif ext.lower() == '.jpg':
            img = tf.image.decode_jpeg(tf.read_file(img_path), channels=3)
        else:
            raise Exception('cannot process {} file.'.format(ext.lower()))
        return img, filename

    # 转换图片通道，padding图片到指定大小
    def _pre_process(self, img, h, w):
        # Convert RGB to BGR
        img_r, img_g, img_b = tf.split(axis=2, num_or_size_splits=3, value=img)
        img = tf.cast(tf.concat(axis=2, values=[img_b, img_g, img_r]), dtype=tf.float32)
        # Extract mean.
        img -= self.img_mean
        # padding
        pad_img = tf.image.pad_to_bounding_box(img, 0, 0, h, w)
        pad_img = tf.expand_dims(pad_img, dim=0)
        return pad_img

    def run(self, image_path):
        # 读入图片数据
        img, filename = self._load_img(image_path)
        # 输出预测的结果
        predictions_op = self._init_net(img=img)

        sess = tf.Session(config=self.config)
        sess.run(tf.global_variables_initializer())

        # 加载模型
        ckpt = tf.train.get_checkpoint_state(self.log_dir)
        if ckpt and ckpt.model_checkpoint_path:
            loader = tf.train.Saver(var_list=tf.global_variables())
            loader.restore(sess, ckpt.model_checkpoint_path)
            Tools.print_info("Restored model parameters from {}".format(ckpt.model_checkpoint_path))
        else:
            Tools.print_info('No checkpoint file found.')

        # 运行
        predictions = sess.run(predictions_op)

        msk = decode_labels(predictions, num_classes=self.num_classes)
        im = Image.fromarray(msk[0])
        im.save(os.path.join(self.save_dir, filename))
        Tools.print_info('over : result save in {}'.format(os.path.join(self.save_dir, filename)))
        pass

    pass

if __name__ == '__main__':
    Runner(is_flip=False).run("data/bdci/vali/testing1_713_713_713.png")
