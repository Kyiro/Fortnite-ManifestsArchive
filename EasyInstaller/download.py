#!/usr/bin/env python
# coding: utf-8

import argparse
import csv
import json
import logging
import os
import shlex
import subprocess
import time
import requests
import webbrowser

from distutils.util import strtobool
from getpass import getuser
from logging.handlers import QueueListener
from multiprocessing import freeze_support, Queue as MPQueue
from sys import exit, stdout

from legendary import __version__, __codename__
from legendary.core import LegendaryCore
from legendary.models.exceptions import InvalidCredentialsError
from legendary.models.game import SaveGameStatus, VerifyResult
from legendary.utils.cli import get_boolean_choice, sdl_prompt
from legendary.utils.custom_parser import AliasedSubParsersAction
from legendary.utils.lfs import validate_files
from legendary.utils.selective_dl import get_sdl_appname

# todo custom formatter for cli logger (clean info, highlighted error/warning)
logging.basicConfig(
    format='[%(name)s] %(levelname)s: %(message)s',
    level=logging.INFO
)
logger = logging.getLogger('cli')


class LegendaryCLI:
    def __init__(self):
        self.core = LegendaryCore()
        self.logger = logging.getLogger('cli')
        self.logging_queue = None

    def setup_threaded_logging(self):
        self.logging_queue = MPQueue(-1)
        shandler = logging.StreamHandler()
        sformatter = logging.Formatter('[%(name)s] %(levelname)s: %(message)s')
        shandler.setFormatter(sformatter)
        ql = QueueListener(self.logging_queue, shandler)
        ql.start()
        return ql

    def install_game(self, manifest: str, game_folder: str, override_base_url: str):
        game = self.core.get_game('Fortnite', update_meta=True)
        base_game = None

        logger.info('Preparing download...')
        # todo use status queue to print progress from CLI
        # This has become a little ridiculous hasn't it?
        dlm, analysis, igame = self.core.prepare_download(game=game, base_game=base_game, base_path=None,force=None, max_shm=None,max_workers=None, game_folder=game_folder,disable_patching=None,override_manifest=manifest,override_old_manifest=None,override_base_url=override_base_url,platform_override=None,file_prefix_filter=None,file_exclude_filter=None,file_install_tag=None,dl_optimizations=None,dl_timeout=None,repair=None,repair_use_latest=None,disable_delta=None,override_delta_manifest=None)

        # game is either up to date or hasn't changed, so we have nothing to doc
        if not analysis.dl_size:
            logger.info('Download size is 0, the game is either already up to date or has not changed. Exiting...')
            if args.repair_mode and os.path.exists(repair_file):
                igame = self.core.get_installed_game(game.app_name)
                if igame.needs_verification:
                    igame.needs_verification = False
                    self.core.install_game(igame)

                logger.debug('Removing repair file.')
                os.remove(repair_file)
            exit(0)

        logger.info(f'Install size: {analysis.install_size / 1024 / 1024:.02f} MiB')
        compression = (1 - (analysis.dl_size / analysis.uncompressed_dl_size)) * 100
        logger.info(f'Download size: {analysis.dl_size / 1024 / 1024:.02f} MiB '
                    f'(Compression savings: {compression:.01f}%)')
        logger.info(f'Reusable size: {analysis.reuse_size / 1024 / 1024:.02f} MiB (chunks) / '
                    f'{analysis.unchanged / 1024 / 1024:.02f} MiB (unchanged / skipped)')

        res = self.core.check_installation_conditions(analysis=analysis, install=igame, game=game,updating=False,ignore_space_req=None)

        if res.warnings or res.failures:
            logger.info('Installation requirements check returned the following results:')

        if res.warnings:
            for warn in sorted(res.warnings):
                logger.warning(warn)

        if res.failures:
            for msg in sorted(res.failures):
                logger.fatal(msg)
            logger.error('Installation cannot proceed, exiting.')
            exit(1)

        logger.info('Downloads are resumable, you can interrupt the download with '
                    'CTRL-C and resume it using the same command later on.')

        start_t = time.time()

        try:
            # set up logging stuff (should be moved somewhere else later)
            dlm.logging_queue = self.logging_queue
            dlm.proc_debug = None

            dlm.start()
            dlm.join()
        except Exception as e:
            end_t = time.time()
            logger.info(f'Installation failed after {end_t - start_t:.02f} seconds.')
            logger.warning(f'The following exception occured while waiting for the donlowader to finish: {e!r}. '
                           f'Try restarting the process, the resume file will be used to start where it failed. '
                           f'If it continues to fail please open an issue on GitHub.')
        else:
            end_t = time.time()
            logger.info(f'Finished installation process in {end_t - start_t:.02f} seconds.')

def main():
    versions = requests.get('https://raw.githubusercontent.com/realkyro/Fortnite-ManifestsArchive/master/Manifests.json').json()
    versions_s = sorted(versions.keys(), key=lambda x: float(str(x.split('-')[1].split('-')[0]).replace('.x', '').replace('Cert', '0')))

    print('\nAvailable manifests:')
    for idx, build_version_string in enumerate(versions_s):
        print(f' * [{idx}] {build_version_string}')
    print(f'\nTotal: {len(versions)}')

    idx = int(input('Please enter the number before the Build Version to select it: '))
    game_folder = input('Please enter a game folder location: ').replace('"', '')

    if '-Windows' in versions_s[idx]:
        override_base_url = 'https://epicgames-download1.akamaized.net/Builds/Fortnite/CloudDir'
    else:
        override_base_url = 'https://epicgames-download1.akamaized.net/Builds/Fortnite/Content/CloudDir'

    cli = LegendaryCLI()
    cli.install_game(versions[versions_s[idx]], game_folder, override_base_url)
    cli.core.exit()
    print("Downloading finished!")
    print("You can close this windows now")
    input()

if __name__ == '__main__':
    # required for pyinstaller on Windows, does nothing on other platforms.
    freeze_support()
    main()