from collections import OrderedDict

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.autograd import Variable
from torch.nn import init
from torch.utils import model_zoo

__all__ = ['ShuffleNetV2',
           'shufflenetv2_x0_5', 'shufflenetv2_x1_0',
           'shufflenetv2_x1_5', 'shufflenetv2_x2_0']

model_urls = {
    'shufflenetv2_x0.5': 'https://github.com/SunDoge/Shufflenet-v2-Pytorch/releases/download/v0.1.0/shufflenetv2_x0.5_60.646_81.696-6692fb04.pth',
    'shufflenetv2_x1.0': 'https://github.com/SunDoge/Shufflenet-v2-Pytorch/releases/download/v0.1.0/shufflenetv2_x1_69.402_88.374-0de6f9e8.pth',
}


def conv_bn(inp, oup, stride):
    return nn.Sequential(
        nn.Conv2d(inp, oup, 3, stride, 1, bias=False),
        nn.BatchNorm2d(oup),
        nn.ReLU(inplace=True)
    )


def conv_1x1_bn(inp, oup):
    return nn.Sequential(
        nn.Conv2d(inp, oup, 1, 1, 0, bias=False),
        nn.BatchNorm2d(oup),
        nn.ReLU(inplace=True)
    )


def channel_shuffle(x, groups):
    batchsize, num_channels, height, width = x.data.size()

    channels_per_group = num_channels // groups

    # reshape
    x = x.view(batchsize, groups,
               channels_per_group, height, width)

    x = torch.transpose(x, 1, 2).contiguous()

    # flatten
    x = x.view(batchsize, -1, height, width)

    return x


class InvertedResidual(nn.Module):
    def __init__(self, inp, oup, stride, benchmodel):
        super(InvertedResidual, self).__init__()
        self.benchmodel = benchmodel
        self.stride = stride
        assert stride in [1, 2]

        oup_inc = oup//2

        if self.benchmodel == 1:
            #assert inp == oup_inc
            self.banch2 = nn.Sequential(
                # pw
                nn.Conv2d(oup_inc, oup_inc, 1, 1, 0, bias=False),
                nn.BatchNorm2d(oup_inc),
                nn.ReLU(inplace=True),
                # dw
                nn.Conv2d(oup_inc, oup_inc, 3, stride,
                          1, groups=oup_inc, bias=False),
                nn.BatchNorm2d(oup_inc),
                # pw-linear
                nn.Conv2d(oup_inc, oup_inc, 1, 1, 0, bias=False),
                nn.BatchNorm2d(oup_inc),
                nn.ReLU(inplace=True),
            )
        else:
            self.banch1 = nn.Sequential(
                # dw
                nn.Conv2d(inp, inp, 3, stride, 1, groups=inp, bias=False),
                nn.BatchNorm2d(inp),
                # pw-linear
                nn.Conv2d(inp, oup_inc, 1, 1, 0, bias=False),
                nn.BatchNorm2d(oup_inc),
                nn.ReLU(inplace=True),
            )

            self.banch2 = nn.Sequential(
                # pw
                nn.Conv2d(inp, oup_inc, 1, 1, 0, bias=False),
                nn.BatchNorm2d(oup_inc),
                nn.ReLU(inplace=True),
                # dw
                nn.Conv2d(oup_inc, oup_inc, 3, stride,
                          1, groups=oup_inc, bias=False),
                nn.BatchNorm2d(oup_inc),
                # pw-linear
                nn.Conv2d(oup_inc, oup_inc, 1, 1, 0, bias=False),
                nn.BatchNorm2d(oup_inc),
                nn.ReLU(inplace=True),
            )

    @staticmethod
    def _concat(x, out):
        # concatenate along channel axis
        return torch.cat((x, out), 1)

    def forward(self, x):
        if 1 == self.benchmodel:
            # x1 = x[:, :(x.shape[1]//2), :, :]
            # x2 = x[:, (x.shape[1]//2):, :, :]
            x1, x2 = x.chunk(2, dim=1)
            out = self._concat(x1, self.banch2(x2))
        elif 2 == self.benchmodel:
            out = self._concat(self.banch1(x), self.banch2(x))

        return channel_shuffle(out, 2)


class ShuffleNetV2(nn.Module):
    def __init__(self, n_class=1000, input_size=224, width_mult=1.):
        super(ShuffleNetV2, self).__init__()

        assert input_size % 32 == 0

        self.stage_repeats = [4, 8, 4]
        # index 0 is invalid and should never be called.
        # only used for indexing convenience.
        if width_mult == 0.5:
            self.stage_out_channels = [-1, 24,  48,  96, 192, 1024]
        elif width_mult == 1.0:
            self.stage_out_channels = [-1, 24, 116, 232, 464, 1024]
        elif width_mult == 1.5:
            self.stage_out_channels = [-1, 24, 176, 352, 704, 1024]
        elif width_mult == 2.0:
            self.stage_out_channels = [-1, 24, 224, 488, 976, 2048]
        else:
            raise ValueError(
                """{} groups is not supported for
                       1x1 Grouped Convolutions""".format(width_mult))

        # building first layer
        input_channel = self.stage_out_channels[1]
        self.conv1 = conv_bn(3, input_channel, 2)
        self.maxpool = nn.MaxPool2d(kernel_size=3, stride=2, padding=1)

        self.features = []
        # building inverted residual blocks
        for idxstage in range(len(self.stage_repeats)):
            numrepeat = self.stage_repeats[idxstage]
            output_channel = self.stage_out_channels[idxstage+2]
            for i in range(numrepeat):
                if i == 0:
                    # inp, oup, stride, benchmodel):
                    self.features.append(InvertedResidual(
                        input_channel, output_channel, 2, 2))
                else:
                    self.features.append(InvertedResidual(
                        input_channel, output_channel, 1, 1))
                input_channel = output_channel

        # make it nn.Sequential
        self.features = nn.Sequential(*self.features)

        # building last several layers
        self.conv_last = conv_1x1_bn(
            input_channel, self.stage_out_channels[-1])
        self.globalpool = nn.Sequential(nn.AvgPool2d(int(input_size/32))) # Why Sequential?
        # self.globalpool = nn.AvgPool2d(int(input_size/32))

        # building classifier
        self.classifier = nn.Sequential(
            nn.Linear(self.stage_out_channels[-1], n_class))
        # self.classifier = nn.Linear(self.stage_out_channels[-1], n_class)

    def forward(self, x):
        x = self.conv1(x)
        x = self.maxpool(x)
        x = self.features(x)
        x = self.conv_last(x)
        x = self.globalpool(x)
        x = x.view(-1, self.stage_out_channels[-1])
        x = self.classifier(x)
        return x


def shufflenetv2(width_mult, n_class=1000, input_size=224, ):
    model = ShuffleNetV2(
        n_class=n_class, input_size=input_size, width_mult=width_mult)
    return model


def shufflenetv2_x0_5(pretrained=False, n_class=1000, input_size=224):
    model = ShuffleNetV2(
        n_class=n_class, input_size=input_size, width_mult=0.5)
    if pretrained:
        model.load_state_dict(model_zoo.load_url(
            model_urls['shufflenetv2_x0.5']))
    return model


def shufflenetv2_x1_0(pretrained=False, n_class=1000, input_size=224):
    model = ShuffleNetV2(
        n_class=n_class, input_size=input_size, width_mult=1.0)
    if pretrained:
        model.load_state_dict(model_zoo.load_url(
            model_urls['shufflenetv2_x1.0']))
    return model


def shufflenetv2_x1_5(pretrained=False, n_class=1000, input_size=224):
    model = ShuffleNetV2(
        n_class=n_class, input_size=input_size, width_mult=1.5)
    # if pretrained:
    #     model.load_state_dict(model_zoo.load_url(
    #         model_urls['shufflenetv2_x1.5']))
    return model


def shufflenetv2_x2_0(pretrained=False, n_class=1000, input_size=224):
    model = ShuffleNetV2(
        n_class=n_class, input_size=input_size, width_mult=2.0)
    # if pretrained:
    #     model.load_state_dict(model_zoo.load_url(
    #         model_urls['shufflenetv2_x2.0']))
    return model


if __name__ == "__main__":
    """Testing
    """
    x = torch.rand(2, 3, 224, 224)
    model = ShuffleNetV2()
    out = model(x)
    print(model)
    print(out.shape)
