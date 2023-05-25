import logging
from typing import Optional

import boto3
from django.conf import settings
from django.core.files.uploadedfile import TemporaryUploadedFile, UploadedFile
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)


class S3BadException(Exception):

    def __init__(self, message: str):
        self.message = message


class S3:
    access_key_id = settings.AWS_ACCESS_KEY_ID
    secret_access_key = settings.AWS_SECRET_ACCESS_KEY
    region_name = settings.AWS_S3_REGION_NAME

    def __init__(self, bucket_name: str, **kwargs):
        self.bucket_name = bucket_name
        for field in ('access_key_id', 'secret_access_key', 'region_name'):
            if field in kwargs:
                setattr(self, field, kwargs[field])
        self.check_params()
        logger.info(f'S3 bucket name - {bucket_name}')
        self.session = self.get_session()

    def check_params(self):
        if not self.bucket_name:
            raise S3BadException(
                _('You not set S3 bucket name in company settings'))
        if not all(
            (self.access_key_id, self.secret_access_key, self.region_name)):
            raise S3BadException(_('Has not AWS credentials'))

    def get_session(self):
        session = boto3.Session(aws_access_key_id=self.access_key_id,
                                aws_secret_access_key=self.secret_access_key,
                                region_name=self.region_name)
        logger.info('S3 - session created')
        return session

    def generate_file_url(self,
                          file: TemporaryUploadedFile or UploadedFile,
                          file_name: Optional[str] = None) -> str:
        return f'https://{self.bucket_name}.s3.{self.region_name}.amazonaws.com/{file_name or file.name}'

    def create_obj(self, file: TemporaryUploadedFile or UploadedFile) -> str:
        """ Uploads django file objects """
        s3 = self.session.client('s3')

        logger.info(
            f'[{self.__class__.__name__}] -> S3 - upload file {file.name} to {self.bucket_name} | '
            f'ContentType: {file.content_type}')

        s3.upload_fileobj(file,
                          self.bucket_name,
                          file.name,
                          ExtraArgs={
                              'ContentType': file.content_type,
                              'ACL': 'public-read'
                          })
        return self.generate_file_url(file)

    def upload_fileobj(self, file, file_name: str, content_type: str = None):
        """ Uploads file-like object without explicit file_name or content_type """
        s3 = self.session.client('s3')
        extra_args = dict(ACL='public-read')
        if content_type:
            extra_args.update(ContentType=content_type)
        logger.info(
            f'[{self.__class__.__name__}] -> S3 - upload file {file_name} to {self.bucket_name} | '
            f'ContentType: {content_type or "Unknown"}')

        s3.upload_fileobj(file,
                          self.bucket_name,
                          file_name,
                          ExtraArgs=extra_args)
        return self.generate_file_url(file, file_name)

    def delete_objs(self, objects: list):
        s3 = self.session.resource('s3')
        bucket = s3.Bucket(self.bucket_name)

        logger.info(f'S3 objects for delete: {objects}')

        response = bucket.delete_objects(Delete={
            'Objects': objects,
            'Quiet': False
        },
                                         RequestPayer='requester')

        logger.info(f'S3 deleting response: {response}')
