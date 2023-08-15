import os
from lxml import etree
from io import StringIO
import requests
import subprocess
import click


def get_tarfiles(tree, db):
    refs = tree.xpath("//a")
    links = [link.get('href', '') for link in refs]
    return [l for l in links if l.startswith(f'{db}.') and l.endswith('.tar.gz')]


def get_checksums(tree, db):
    refs = tree.xpath("//a")
    links = [link.get('href', '') for link in refs]
    return [l for l in links if l.startswith(f'{db}.') and l.endswith('.tar.gz.md5')]


def download_file(url, out_path):
    subprocess.run(['wget', '--retry-connrefused', '--waitretry=1', '--tries=3',
                    '-O', out_path, url], check=True)


def check_the_sum(tar_path, check_path):
    tar_resp = subprocess.run(['md5sum', tar_path], check=True, stdout=subprocess.PIPE)
    check_resp = subprocess.run(['cat', check_path], check=True, stdout=subprocess.PIPE)
    tar_sum = tar_resp.stdout.decode('utf-8').split(' ')[0]
    check_sum = check_resp.stdout.decode('utf-8').split(' ')[0]
    assert tar_sum == check_sum


@click.command()
@click.argument('work_dir', type=click.Path(exists=True), required=True)
@click.option('--db', type=str, required=True,
              help='Database name to download.')
def main(work_dir, db):
    parser = etree.HTMLParser()

    url = 'https://ftp.ncbi.nlm.nih.gov/blast/db/'
    page = requests.get(url)
    html = page.content.decode("utf-8")

    tree = etree.parse(StringIO(html), parser=parser)

    tar_files = get_tarfiles(tree, db)
    checksums = get_checksums(tree, db)

    if len(tar_files) == 0 or len(checksums) == 0 or len(tar_files) != len(checksums):
        raise SystemExit(
                'Something is wrong with the database files. ' 
                f'Check on {url} if the {db} database files present and ' 
                'there is a corresponding .tar.gz.md5 for each .tar.gz'
                )

    os.chdir(work_dir)

    for tar, check in zip(sorted(tar_files), sorted(checksums)):

        tar_base = '.'.join(tar.split('.')[:-2])   # cut .tar.gz
        check_base = '.'.join(check.split('.')[:-3])   # cut .tar.gz.md5
        assert tar_base == check_base

        tar_path = os.path.join(os.getcwd(), tar)
        check_path = os.path.join(os.getcwd(), check)

        print(f'\nDownloading {check}...\n')
        download_file(os.path.join(url, check), check_path)

        if not os.path.exists(tar_path):
            print(f'\nDownloading {tar}...\n')
            download_file(os.path.join(url, tar), tar_path)

        try:
            check_the_sum(tar_path, check_path)
        except AssertionError:
            print(f'\nThe {tar} is broken or imcomplete. Downloading again...\n')
            download_file(os.path.join(url, tar), tar_path)
            check_the_sum(tar_path, check_path)

        print(f'\nDecompressing {tar}...\n')
        subprocess.run(['tar', '-xzvf', tar_path], check=True)


if __name__ == '__main__':
    main()

