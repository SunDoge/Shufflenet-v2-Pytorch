# Shufflenet-v2-Pytorch 

## Introduction

This is a Pytorch implementation of faceplusplus's ShuffleNet-v2. For details, please read the following papers: 

[ShuffleNet V2: Practical Guidelines for Efficient CNN Architecture Design](https://arxiv.org/abs/1807.11164)

## Pretrained Models on ImageNet

We provide pretrained ShuffleNet-v2 models on ImageNet,which achieve slightly better accuracy rates than the original ones reported in the paper.

The top-1/5 accuracy rates by using single center crop (crop size: 224x224, image size: 256xN): 

| Network            | Top-1  | Top-5  | Top-1(reported in the paper) |
| ------------------ | ------ | ------ | ---------------------------- |
| ShuffleNet-v2-x0.5 | 60.646 | 81.696 | 60.300                       |
| ShuffleNet-v2-x1   | 69.402 | 88.374 | 69.400                       |


## Evaluate Models 

```
python eval.py -a shufflenetv2 --width_mult=0.5 --evaluate=./shufflenetv2_x0.5_60.646_81.696.pth.tar ./ILSVRC2012/
```

```
python eval.py -a shufflenetv2 --width_mult=1.0 --evaluate=./shufflenetv2_x1_69.390_88.412.pth.tar ./ILSVRC2012/
```

## Version:

- Python2.7
- torch0.3.1
- torchvision0.2.1

Dataset prepare Refer to https://github.com/facebook/fb.resnet.torch/blob/master/INSTALL.md#download-the-imagenet-dataset


## Roadmap

- [x] Change python version to 3.x
- [x] Change pytorch version to 0.4.x and 1.0
- [ ] Retrain and release new pretrain model
