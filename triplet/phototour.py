import os
import errno
import numpy as np

import cv2

import torch
import torch.utils.data as data


class PhotoTour(data.Dataset):
    urls = {
        'notredame': 'http://www.iis.ee.ic.ac.uk/~vbalnt/phototourism-patches/notredame.zip',
        'yosemite': 'http://www.iis.ee.ic.ac.uk/~vbalnt/phototourism-patches/yosemite.zip',
        'liberty': 'http://www.iis.ee.ic.ac.uk/~vbalnt/phototourism-patches/liberty.zip'
    }
    mean = {'notredame': 0.4854, 'yosemite': 0.4844, 'liberty': 0.4437}
    std = {'notredame': 0.1864, 'yosemite': 0.1818, 'liberty': 0.2019}
    lens = {'notredame': 468159, 'yosemite': 633587, 'liberty': 450092}

    image_ext = 'bmp'
    info_file = 'info.txt'
    matches_files = 'm50_100000_100000_0.txt'

    def __init__(self, root, name, download=False, size=None):
        self.root = root
        self.size = size or 64

        self.name = name
        self.data_dir = os.path.join(root, name)
        self.data_down = os.path.join(root, '{}.zip'.format(name))
        self.data_file = os.path.join(root, '{}_{}.pt'.format(name, self.size))

        self.mean = self.mean[name]
        self.std = self.std[name]

        if download:
            self.download()

        if not self._check_exists():
            raise RuntimeError('Dataset not found.'
                               + ' You can use download=True to download it')

        # load the serialized data
        self.data, self.labels, self.matches = torch.load(self.data_file)

    def __getitem__(self, index):
        return self.data[index]

    def __len__(self):
        return self.lens[self.name]

    def _check_exists(self):
        return os.path.exists(self.data_file)

    def _check_downloaded(self):
        return os.path.exists(self.data_dir)

    def download(self):
        print_('\n-- Loading PhotoTour dataset: {}\n'.format(self.name))

        if self._check_exists():
            print_('Found cached data {}'.format(self.data_file))
            return

        # download files
        try:
            os.makedirs(self.root)
        except OSError as e:
            if e.errno == errno.EEXIST:
                pass
            else:
                raise

        if not self._check_downloaded():
            url = self.urls[self.name]
            filename = url.rpartition('/')[2]
            file_path = os.path.join(self.root, filename)

            if not os.path.exists(file_path):
                print_('Downloading {}\nDownloading {}\n\nIt might take while. '
                       'Please grab yourself a coffee and relax.\n'
                       .format(url, file_path))

                os.system('wget {} -P {}'.format(url, self.root))

            print_('Extracting data {}\n'.format(self.data_down))

            import zipfile
            with zipfile.ZipFile(file_path, 'r') as z:
                z.extractall(self.data_dir)
            os.unlink(file_path)

        # process and save as torch files
        print_('Caching data {}'.format(self.data_file))

        data_set = (
            read_image_file(self.data_dir, self.image_ext, self.size, self.lens[self.name]),
            read_info_file(self.data_dir, self.info_file),
            read_matches_files(self.data_dir, self.matches_files)
        )

        with open(self.data_file, 'wb') as f:
            torch.save(data_set, f)


def print_(text):
    print('\033[;1m{}\033[0;0m'.format(text))


def read_image_file(data_dir, image_ext, img_sz, n):
    """Return a Tensor containing the patches
    """
    def PIL2array(_img, img_size):
        """Convert PIL image type to numpy 2D array
        """
        return np.array(_img.getdata(), dtype=np.uint8) \
            .reshape(img_size, img_size)

    def read_filenames(_data_dir, _image_ext):
        """Return a list with the file names of the images containing the patches
        """
        files = []
        # find those files with the specified extension
        for file_dir in os.listdir(_data_dir):
            if file_dir.endswith(_image_ext):
                files.append(os.path.join(_data_dir, file_dir))
        return sorted(files)  # sort files in ascend order to keep relations

    images = []
    list_files = read_filenames(data_dir, image_ext)

    # using opencv to read  dataset
    for file_path in list_files:
        # load the image containing the patches, crop in 64x64 patches and
        # reshape to the desired size (default: 64)
        img = cv2.imread(file_path, cv2.IMREAD_GRAYSCALE)
        for y in range(0, 1024, 64):
            for x in range(0, 1024, 64):
                patch = img[y: y + 64, x: x + 64]
                if img_sz != 64:
                    patch = cv2.resize(patch, (img_sz, img_sz), cv2.INTER_LINEAR)
                images.append(patch)
    return torch.ByteTensor(np.array(images[:n]))


def read_info_file(data_dir, info_file):
    """Return a Tensor containing the list of labels
       Read the file and keep only the ID of the 3D point.
    """
    labels = []
    with open(os.path.join(data_dir, info_file), 'r') as f:
        for line in f:
            labels.append(int(line.split()[0]))
    return torch.LongTensor(np.array(labels))


def read_matches_files(data_dir, matches_file):
    """Return a Tensor containing the ground truth matches
       Read the file and keep only 3D point ID.
       Matches are represented with a 1, non matches with a 0.
    """
    matches = []
    with open(os.path.join(data_dir, matches_file), 'r') as f:
        for line in f:
            l = line.split()
            matches.append([int(l[0]), int(l[3]), int(l[1] == l[4])])
    return torch.LongTensor(np.array(matches))


if __name__ == '__main__':
    dataset = PhotoTour(root='/home/eriba/datasets/patches_dataset',
                        name='yosemite',
                        download=True,
                        size=32)

    print('Loaded PhotoTour: {} with {} images.'
          .format(dataset.name, len(dataset.data)))

    assert len(dataset.data) == len(dataset.labels)