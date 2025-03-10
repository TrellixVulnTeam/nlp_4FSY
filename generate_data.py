import csv
import os
import re
import random
import pandas as pd
import tqdm
import jieba

label2class = {
    "财经": "高风险",
    "时政": "高风险",
    "房产": "中风险",
    "科技": "中风险",
    "教育": "低风险",
    "时尚": "低风险",
    "游戏": "低风险",
    "家居": "可公开",
    "体育": "可公开",
    "娱乐": "可公开",
}
label2num = {
    "财经": 0,
    "时政": 1,
    "房产": 2,
    "科技": 3,
    "教育": 4,
    "时尚": 5,
    "游戏": 6,
    "家居": 7,
    "体育": 8,
    "娱乐": 9,
}

# 句子的结束标识
token_ends = ['。', '？', '！', '；', '  ', '》', '】', ']', '}', ')', '.', '?', '!', ';', '\u3000', '\t', '\n']

# 句子最长的长度
max_length = 128
min_length = 10

# 三个数据集比例
train_data_percent = 0.8
dev_data_percent = 0.1
test_data_percent = 0.1

# 对数据集切割方法
# 1 -> 切成很多段
# 2 -> 不切割
# 3 -> 切成最多三段
# 4 -> 提取重要的句子
cut_type = 4


# [(id, class_name, para)]
def read_labeled_csv(input_filename):
    with open(input_filename, 'r', encoding="utf-8") as fin:
        data = []
        cnt = 0
        for line in fin:
            cnt += 1
            if cnt == 1:
                continue
            pos = line.find(',')
            id = line[0:pos]
            # print(id)
            id = int(id)
            class_name = line[pos + 1:pos + 3]
            text = line[pos + 4:]
            data.append((id, class_name, text))
    return data


# [(id, para)]
def read_unlabeled_csv(input_filename):
    with open(input_filename, 'r') as fin:
        data = []
        cnt = 0
        for line in fin:
            cnt += 1
            if cnt == 1:
                continue
            pos = line.find(',')
            id = line[0:pos]
            # print(id)
            id = int(id)
            text = line[pos + 1:]
            data.append((id, text))
    return data


# 过滤停用词
def filter_stop_words(para):
    # punc = '~`!#$%^&*()_+-=|\';":/.,?><~·！@#￥%……&*（）——+-=“：’；、。，？》《{}'
    # para = jieba.cut(re.sub(r"[%s]+" % punc, "", content), cut_all=False)
    para = re.sub('(\u3000{2})([^”’])', r"\1\n\2", para)  # 全角空白符
    para = re.sub('(\u3000)([^”’])', r"\1\n\2", para)  # 全角空白符
    para = re.sub('(\xa0{2})([^”’])', r"\1\n\2", para)  # 不间断空白符
    para = re.sub('(\xa0)([^”’])', r"\1\n\2", para)  # 不间断空白符
    para = re.sub('(\t{2})([^”’])', r"\1\n\2", para)  # \t
    para = re.sub('(\t)([^”’])', r"\1\n\2", para)  # \t
    para = re.sub('(\n{2})([^”’])', r"\1\n\2", para)  # \n
    para = re.sub('(\n)([^”’])', r"\1\n\2", para)  # \n
    para = re.sub('([。！？\?])([^”’])', r"\1\n\2", para)  # 单字符断句符
    para = re.sub('(\.{6})([^”’])', r"\1\n\2", para)  # 英文省略号
    para = re.sub('(\…{2})([^”’])', r"\1\n\2", para)  # 中文省略号
    para = re.sub('(\t)([^”’])', r"\1\n\2", para)  # \t
    para = re.sub('([。！？\?][”’】}])([^，。！？\?])', r'\1\n\2', para)
    # 如果双引号前有终止符，那么双引号才是句子的终点，把分句符\n放到双引号后，注意前面的几句都小心保留了双引号
    para = para.rstrip()  # 段尾如果有多余的\n就去掉它
    para = para.replace(' ', '')
    para = para.replace('\t', '')
    # para = para.replace('\n', '')
    para = para.replace('\u3000', '')
    para = para.replace('\xa0', '')
    para = para.replace('\xad', '')
    from stopWord.stop_word import del_stop_word
    del_stop_word(para)
    return para


# 把很长的一段话分成符合bert长度要求的若干段话
def cut_para_many_times(para):
    if len(para) < max_length:
        para = filter_stop_words(para)
        para = list(map(str, para.split('\n')))
        return para
    para = filter_stop_words(para)
    para = list(map(str, para.split('\n')))
    ans = []
    i = 0
    while i < len(para):
        length = len(para[i])
        paras = para[i]
        while i + 1 < len(para) and length + len(para[i + 1]) < max_length:
            i += 1
            paras += para[i]
            length += len(para[i])
        ans.append(paras)
        i += 1
    return ans


# 不切割只过滤停用词
def filter_para(para):
    para = filter_stop_words(para)
    para = para.replace('\n', '')
    return [para]


# 分成x段, x <= 3?
# 可能会捕捉到头尾以及中间的信息
def cut_para_few_times(para, times=3):
    def deal_with_pref(para2):
        pos = para2.find('。')
        pos = min(pos, para2.find('！'))
        pos = min(pos, para2.find('？'))
        pos = min(pos, para2.find('?'))
        pos = min(pos, para2.find('.'))
        return para2[pos + 1:]

    if times == 1 or times == 2 or times == 3:
        pass
    else:
        raise ValueError
    if len(para) < max_length:
        para = filter_stop_words(para)
        return [para.replace('\n', '')]
    while times * max_length > len(para) and times > 1:
        times -= 1
    if times == 1:
        para = filter_stop_words(para)
        return [para.replace('\n', '')]
    elif times == 2:
        para1 = filter_stop_words(para[:len(para) // 2])
        para2 = filter_stop_words(para[len(para) // 2 + 1:])
        para2 = deal_with_pref(para2)
        return [para1.replace('\n', ''), para2.replace('\n', '')]
    else:
        para1 = filter_stop_words(para[:len(para) // 3])
        para2 = filter_stop_words(para[len(para) // 3 + 1:len(para) // 3 * 2])
        para3 = filter_stop_words(para[len(para) // 3 * 2 + 1:])
        para2 = deal_with_pref(para2)
        para3 = deal_with_pref(para3)
        return [para1.replace('\n', ''), para2.replace('\n', ''), para3.replace('\n', '')]


def sort_dict(dicts, count):
    # 获取前几名的key
    final_result = []
    sorted_dic = sorted([(k, v) for k, v in dicts.items()], reverse=True)
    t_set = set()
    for item in sorted_dic:
        t_set.add(item[1])
    for list_item in sorted(t_set, reverse=True)[:count]:
        for dic_item in sorted_dic:
            if dic_item[1] == list_item:
                final_result.append(dic_item[0])
    return final_result


def cut_para_by_summary(para):
    para = filter_stop_words(para)
    para = para.replace('\n', '')
    para = para.replace("\u2003", "")
    sentences = re.split('。|！|\!|\.|？|\?|；', para)  # 切分一句话
    word2count = {}
    for word in jieba.cut(para):  # 一句话分词

        if word not in word2count.keys():
            word2count[word] = 1
        else:
            word2count[word] += 1
    for key in word2count.keys():
        word2count[key] = word2count[key] / max(word2count.values())
    # print(word2count)
    sent2score = {}
    for sentence in sentences:
        for word in jieba.cut(sentence):
            if word in word2count.keys():
                if len(sentence) < 300:
                    if sentence not in sent2score.keys():
                        sent2score[sentence] = word2count[word]
                    else:
                        sent2score[sentence] += word2count[word]
    # print(sent2score)
    para = sort_dict(sent2score, 1)  # 可以生成相关的前几个句子，这里感觉还是越精简越好一些
    return para


def read_cnews_txt(input_file):
    data = []
    with open(input_file, 'r', encoding="utf-8") as fin:
        for line in fin:
            x, y = line.split('\t')
            y = y.replace('\t', '')
            y = y.replace('\n', '')
            y = y.replace('\u3000', '')
            y = y.replace('\xa0', '')
            if len(y) < min_length:
                continue
            data.append((y, label2num[x]))
    print('test_data : ')
    # print(data)
    return data


def main():
    labeled_data = read_labeled_csv('real/data/labeled_data_with_10_classes.csv')

    data = []

    print('filter stop words ...')
    # 切割段落生成多个data
    for id, label, para in labeled_data:
        if cut_type == 1:
            para = cut_para_many_times(para)
        elif cut_type == 2:
            para = filter_para(para)
        elif cut_type == 3:
            para = cut_para_few_times(para)
        elif cut_type == 4:
            para = cut_para_by_summary(para)
        else:
            raise ValueError
        for x in para:
            if len(x) < min_length:
                continue
            if x in token_ends:
                continue
            data.append((x, label2num[label]))
        # print(para)

    print('Done!')

    print('\nwriting class.txt ...')
    # 写class.txt
    with open('real/data/class.txt', 'w') as fout:
        for x in label2num:
            fout.write(x + '\n')
    print('Done!')

    random.shuffle(data)

    # 测试集换成新的
    train_data = data[:int(train_data_percent * len(data))]
    dev_data = data[int(train_data_percent * len(data)):]
    test_data = read_cnews_txt('cnews/cnews.test.txt')

    print('\ndata size:', len(data))
    print('train_data size:', len(train_data))
    print('dev_data size:', len(dev_data))
    print('test_data size:', len(test_data))
    print('\nwriting train/dev/test data ...')
    with open('real/data/train.txt', 'w', encoding="utf-8") as fout:
        for x, y in train_data:
            if len(x) > 2:
                fout.write(x + '\t' + str(y) + '\n')
    with open('real/data/dev.txt', 'w', encoding="utf-8") as fout:
        for x, y in dev_data:
            if len(x) > 2:
                fout.write(x + '\t' + str(y) + '\n')
    with open('real/data/test.txt', 'w', encoding="utf-8") as fout:
        for x, y in test_data:
            if len(x) > 2:
                fout.write(x + '\t' + str(y) + '\n')
    # 后续作文本增强的生成的文件
    # with open('real/data/train2.txt', 'w', encoding="utf-8") as fout:
    #     for x, y in train_data:
    #         if len(x) > 2:
    #             fout.write(str(y) + '\t' + x + '\n')
    print('Done!')


if __name__ == '__main__':
    main()
