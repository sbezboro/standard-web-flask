from datetime import datetime
import gzip
import os

from boto.s3.connection import S3Connection
from boto.s3.key import Key
import rollbar

from standardweb import app
from standardweb import celery


@celery.task()
def db_backup():
    backup_dir = '/tmp/db_backups/'

    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)

    # delete old backups
    for f in os.listdir(backup_dir):
        path = os.path.join(backup_dir, f)
        if os.path.isfile(path):
            os.unlink(path)

    filename = datetime.utcnow().strftime('backup-%Y-%m-%d-%H-%M-%S.sql')
    backup_path = os.path.join(backup_dir, filename)

    password = ' -p' + app.config['DB_BACKUP_PASSWORD'] if app.config['DB_BACKUP_PASSWORD'] else ''

    # do the backup
    os.system(
        'mysqldump -u ' +
        app.config['DB_BACKUP_USER'] +
        password +
        ' standardsurvival > ' +
        backup_path
    )

    gzip_filename = filename + '.gz'
    gzip_backup_path = os.path.join(backup_dir, gzip_filename)

    # gzip the backup
    with open(backup_path, 'rb') as f_in:
        with gzip.open(gzip_backup_path, 'wb') as f_out:
            f_out.writelines(f_in)

    # upload to S3
    conn = S3Connection(app.config['AWS_ACCESS_KEY_ID'], app.config['AWS_SECRET_ACCESS_KEY'])
    bucket = conn.get_bucket(app.config['BACKUP_BUCKET_NAME'], validate=False)
    key = Key(bucket)
    key.key = 'mysql/' + gzip_filename

    key.set_contents_from_filename(gzip_backup_path, reduced_redundancy=True)

    rollbar.report_message('Database backup complete', level='info', extra_data={
        'filename': gzip_filename,
    })
