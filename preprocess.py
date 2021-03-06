import os
import sys
import logging
import argparse
import json
import random
import numpy as np
from utils import calculate_cmvn, convert_to, read_binary_file, write_binary_file

with open('./hparams.json', 'r') as f:
    hparams = json.load(f)

logger = logging.getLogger(__name__)

train_ratio = 0.97
valid_ratio = 0.02
test_ratio = 0.01

cur_file = os.path.dirname(os.path.realpath(__file__))


def get_random_scp(label_scp_dir, param_scp_dir, lst_dir):
    label_scp = open(label_scp_dir + 'all.scp')
    param_scp = open(param_scp_dir + 'all.scp')

    label_train = open(label_scp_dir + 'train.scp', 'w')
    label_valid = open(label_scp_dir + 'valid.scp', 'w')
    label_test = open(label_scp_dir + 'test.scp', 'w')
    param_train = open(param_scp_dir + 'train.scp', 'w')
    param_valid = open(param_scp_dir + 'valid.scp', 'w')
    param_test = open(param_scp_dir + 'test.scp', 'w')

    if not os.path.exists(lst_dir):
        os.mkdir(lst_dir)

    lst_train = open(os.path.join(lst_dir, 'train.lst'), 'w')
    lst_valid = open(os.path.join(lst_dir, 'valid.lst'), 'w')
    lst_test = open(os.path.join(lst_dir, 'test.lst'), 'w')

    lists_label = label_scp.readlines()
    lists_param = param_scp.readlines()

    if len(lists_label) != len(lists_param):
        print("scp files have unequal lengths")
        sys.exit(1)

    lists = list(range(len(lists_label)))
    random.seed(0)
    random.shuffle(lists)

    train_num = int(train_ratio * len(lists))
    valid_num = int(valid_ratio * len(lists))
    test_num = int(test_ratio * len(lists))
    train_lists = sorted(lists[: train_num])
    valid_lists = sorted(lists[train_num: (train_num + valid_num)])
    test_lists = sorted(lists[(train_num + valid_num):])

    for i in range(len(lists)):
        line_label = lists_label[i]
        line_param = lists_param[i]
        line_lst = line_label.strip() + ' ' + line_param.split()[1] + '\n'
        if i in valid_lists:
            label_valid.write(line_label)
            param_valid.write(line_param)
            lst_valid.write(line_lst)
        elif i in test_lists:
            label_test.write(line_label)
            param_test.write(line_param)
            lst_test.write(line_label)
        else:
            label_train.write(line_label)
            param_train.write(line_param)
            lst_train.write(line_lst)


def create_scp(raw):
    label_dir = os.path.join(cur_file, raw, 'prepared_label')
    cmp_dir = os.path.join(cur_file, raw, 'prepared_cmp')

    if not os.path.exists(label_dir):
        os.mkdir(label_dir)
    if not os.path.exists(cmp_dir):
        os.mkdir(cmp_dir)

    label_files = os.listdir(label_dir)
    cmp_files = os.listdir(cmp_dir)

    if not os.path.exists(os.path.join(label_dir, 'label_scp')):
        os.mkdir(os.path.join(label_dir, 'label_scp'))
    if not os.path.exists(os.path.join(cmp_dir, 'param_scp')):
        os.mkdir(os.path.join(cmp_dir, 'param_scp'))

    label_all_scp = open(os.path.join(os.path.join(label_dir, 'label_scp'), 'all.scp'), 'w')
    param_all_scp = open(os.path.join(os.path.join(cmp_dir, 'param_scp'), 'all.scp'), 'w')

    for label_filename in label_files:
        if label_filename == 'label_scp':
            continue
        filename = os.path.splitext(label_filename)[0]
        cmp_filename = os.path.splitext(label_filename)[0] + '.cmp'
        label_file_path = os.path.join(label_dir, label_filename)
        label_all_scp.write(filename + " " + label_file_path + '\n')

        cmp_file_path = os.path.join(cmp_dir, cmp_filename)
        param_all_scp.write(filename + " " + cmp_file_path + "\n")


def read_data(args, raw):
    label_dir = os.path.join(cur_file, raw, 'prepared_label')
    cmp_dir = os.path.join(cur_file, raw, 'prepared_cmp')

    if os.path.exists(label_dir) and os.path.exists(cmp_dir):
        logger.info('Raw data has been prepared.')
        return

    if not os.path.exists(label_dir):
        os.mkdir(label_dir)
    if not os.path.exists(cmp_dir):
        os.mkdir(cmp_dir)

    label_files = os.listdir(args.label_dir)
    cmp_files = os.listdir(args.cmp_dir)

    # Do frame alignment
    for line in label_files:
        filename, _ = os.path.splitext(line.strip())
        logger.info('processing ' + filename)
        sys.stdout.flush()

        label_mat = np.loadtxt(os.path.join(args.label_dir, filename + '.lab'))
        if args.model_type == 'acoustic':
            cmp_mat = read_binary_file(
                os.path.join(args.cmp_dir, filename + ".cmp"),
                dimension=hparams['target_channels'], dtype=np.float64)
        elif args.model_type == 'acoustic_mgc':
            cmp_mat = read_binary_file(
                os.path.join(args.cmp_dir, filename + ".cmp"),
                dimension=hparams['mgc_target_channels'], dtype=np.float32)

        if label_mat.shape[0] <= cmp_mat.shape[0]:
            cmp_mat = cmp_mat[:label_mat.shape[0], :]
        else:
            frame_diff = label_mat.shape[0] - cmp_mat.shape[0]
            rep = np.repeat(cmp_mat[-1:, :], frame_diff, axis=0)
            cmp_mat = np.concatenate([cmp_mat, rep], axis=0)

        write_binary_file(
            label_mat,
            os.path.join(label_dir, filename + '.lab'))
        if args.model_type == 'acoustic':
            write_binary_file(
                cmp_mat,
                os.path.join(cmp_dir, filename + '.cmp'), dtype=np.float64)
        elif args.model_type == 'acoustic_mgc':
            write_binary_file(
                cmp_mat,
                os.path.join(cmp_dir, filename + '.cmp'), dtype=np.float32)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--label_dir', type=str)
    parser.add_argument('--cmp_dir', type=str)
    parser.add_argument('--name', type=str)
    parser.add_argument('--model_type', type=str)
    args = parser.parse_args()

    logging.basicConfig(format='%(asctime)s %(filename)s %(levelname)s %(message)s',
                        datefmt='%a, %d %b %Y %H:%M:%S', level=logging.INFO,
                        stream=sys.stdout)

    raw = 'raw_' + args.name

    if not os.path.exists(raw):
        os.mkdir(raw)

    label_scp_dir = raw + '/prepared_label/label_scp/'
    param_scp_dir = raw + '/prepared_cmp/param_scp/'
    lst_dir = os.path.join(cur_file, 'config_' + args.name)
    data_dir = os.path.join(cur_file, 'data_' + args.name)

    read_data(args, raw)
    create_scp(raw)
    get_random_scp(label_scp_dir, param_scp_dir, lst_dir)
    # cal cmvn to the data
    calculate_cmvn('train', lst_dir, data_dir, args.model_type)
    convert_to('train', os.path.join(lst_dir, 'train'), data_dir, args.model_type)
    convert_to('valid', os.path.join(lst_dir, 'valid'), data_dir, args.model_type)
    convert_to('test', os.path.join(lst_dir, 'test'), data_dir, args.model_type)


if __name__ == '__main__':
    main()
import os
import sys
import logging
import argparse
import json
import random
import numpy as np
from utils import calculate_cmvn, convert_to, read_binary_file, write_binary_file

with open('./hparams.json', 'r') as f:
    hparams = json.load(f)

logger = logging.getLogger(__name__)

train_ratio = 0.97
valid_ratio = 0.02
test_ratio = 0.01

cur_file = os.path.dirname(os.path.realpath(__file__))


def get_random_scp(label_scp_dir, param_scp_dir, lst_dir):
    label_scp = open(label_scp_dir + 'all.scp')
    param_scp = open(param_scp_dir + 'all.scp')

    label_train = open(label_scp_dir + 'train.scp', 'w')
    label_valid = open(label_scp_dir + 'valid.scp', 'w')
    label_test = open(label_scp_dir + 'test.scp', 'w')
    param_train = open(param_scp_dir + 'train.scp', 'w')
    param_valid = open(param_scp_dir + 'valid.scp', 'w')
    param_test = open(param_scp_dir + 'test.scp', 'w')

    if not os.path.exists(lst_dir):
        os.mkdir(lst_dir)

    lst_train = open(os.path.join(lst_dir, 'train.lst'), 'w')
    lst_valid = open(os.path.join(lst_dir, 'valid.lst'), 'w')
    lst_test = open(os.path.join(lst_dir, 'test.lst'), 'w')

    lists_label = label_scp.readlines()
    lists_param = param_scp.readlines()

    if len(lists_label) != len(lists_param):
        print("scp files have unequal lengths")
        sys.exit(1)

    lists = list(range(len(lists_label)))
    random.seed(0)
    random.shuffle(lists)

    train_num = int(train_ratio * len(lists))
    valid_num = int(valid_ratio * len(lists))
    test_num = int(test_ratio * len(lists))
    train_lists = sorted(lists[: train_num])
    valid_lists = sorted(lists[train_num: (train_num + valid_num)])
    test_lists = sorted(lists[(train_num + valid_num):])

    for i in range(len(lists)):
        line_label = lists_label[i]
        line_param = lists_param[i]
        line_lst = line_label.strip() + ' ' + line_param.split()[1] + '\n'
        if i in valid_lists:
            label_valid.write(line_label)
            param_valid.write(line_param)
            lst_valid.write(line_lst)
        elif i in test_lists:
            label_test.write(line_label)
            param_test.write(line_param)
            lst_test.write(line_label)
        else:
            label_train.write(line_label)
            param_train.write(line_param)
            lst_train.write(line_lst)


def create_scp(raw):
    label_dir = os.path.join(cur_file, raw, 'prepared_label')
    cmp_dir = os.path.join(cur_file, raw, 'prepared_cmp')

    if not os.path.exists(label_dir):
        os.mkdir(label_dir)
    if not os.path.exists(cmp_dir):
        os.mkdir(cmp_dir)

    label_files = os.listdir(label_dir)
    cmp_files = os.listdir(cmp_dir)

    if not os.path.exists(os.path.join(label_dir, 'label_scp')):
        os.mkdir(os.path.join(label_dir, 'label_scp'))
    if not os.path.exists(os.path.join(cmp_dir, 'param_scp')):
        os.mkdir(os.path.join(cmp_dir, 'param_scp'))

    label_all_scp = open(os.path.join(os.path.join(label_dir, 'label_scp'), 'all.scp'), 'w')
    param_all_scp = open(os.path.join(os.path.join(cmp_dir, 'param_scp'), 'all.scp'), 'w')

    for label_filename in label_files:
        if label_filename == 'label_scp':
            continue
        filename = os.path.splitext(label_filename)[0]
        cmp_filename = os.path.splitext(label_filename)[0] + '.cmp'
        label_file_path = os.path.join(label_dir, label_filename)
        label_all_scp.write(filename + " " + label_file_path + '\n')

        cmp_file_path = os.path.join(cmp_dir, cmp_filename)
        param_all_scp.write(filename + " " + cmp_file_path + "\n")


def read_data(args, raw):
    label_dir = os.path.join(cur_file, raw, 'prepared_label')
    cmp_dir = os.path.join(cur_file, raw, 'prepared_cmp')

    if os.path.exists(label_dir) and os.path.exists(cmp_dir):
        logger.info('Raw data has been prepared.')
        return

    if not os.path.exists(label_dir):
        os.mkdir(label_dir)
    if not os.path.exists(cmp_dir):
        os.mkdir(cmp_dir)

    label_files = os.listdir(args.label_dir)
    cmp_files = os.listdir(args.cmp_dir)

    # Do frame alignment
    for line in label_files:
        filename, _ = os.path.splitext(line.strip())
        logger.info('processing ' + filename)
        sys.stdout.flush()

        label_mat = np.loadtxt(os.path.join(args.label_dir, filename + '.lab'))
        if args.model_type == 'acoustic':
            cmp_mat = read_binary_file(
                os.path.join(args.cmp_dir, filename + ".cmp"),
                dimension=hparams['target_channels'], dtype=np.float64)
        elif args.model_type == 'acoustic_mgc':
            cmp_mat = read_binary_file(
                os.path.join(args.cmp_dir, filename + ".cmp"),
                dimension=hparams['mgc_target_channels'], dtype=np.float32)

        if label_mat.shape[0] <= cmp_mat.shape[0]:
            cmp_mat = cmp_mat[:label_mat.shape[0], :]
        else:
            frame_diff = label_mat.shape[0] - cmp_mat.shape[0]
            rep = np.repeat(cmp_mat[-1:, :], frame_diff, axis=0)
            cmp_mat = np.concatenate([cmp_mat, rep], axis=0)

        write_binary_file(
            label_mat,
            os.path.join(label_dir, filename + '.lab'))
        if args.model_type == 'acoustic':
            write_binary_file(
                cmp_mat,
                os.path.join(cmp_dir, filename + '.cmp'), dtype=np.float64)
        elif args.model_type == 'acoustic_mgc':
            write_binary_file(
                cmp_mat,
                os.path.join(cmp_dir, filename + '.cmp'), dtype=np.float32)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--label_dir', type=str)
    parser.add_argument('--cmp_dir', type=str)
    parser.add_argument('--name', type=str)
    parser.add_argument('--model_type', type=str)
    args = parser.parse_args()

    logging.basicConfig(format='%(asctime)s %(filename)s %(levelname)s %(message)s',
                        datefmt='%a, %d %b %Y %H:%M:%S', level=logging.INFO,
                        stream=sys.stdout)

    raw = 'raw_' + args.name

    if not os.path.exists(raw):
        os.mkdir(raw)

    label_scp_dir = raw + '/prepared_label/label_scp/'
    param_scp_dir = raw + '/prepared_cmp/param_scp/'
    lst_dir = os.path.join(cur_file, 'config_' + args.name)
    data_dir = os.path.join(cur_file, 'data_' + args.name)

    read_data(args, raw)
    create_scp(raw)
    get_random_scp(label_scp_dir, param_scp_dir, lst_dir)
    # cal cmvn to the data
    calculate_cmvn('train', lst_dir, data_dir, args.model_type)
    convert_to('train', os.path.join(lst_dir, 'train'), data_dir, args.model_type)
    convert_to('valid', os.path.join(lst_dir, 'valid'), data_dir, args.model_type)
    convert_to('test', os.path.join(lst_dir, 'test'), data_dir, args.model_type)


if __name__ == '__main__':
    main()
