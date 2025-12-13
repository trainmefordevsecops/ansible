pipeline {
    agent {
        label 'mac-machine'
    }

    environment {
        AWS_ACCESS_KEY_ID     = credentials('aws-access-key-id')
        AWS_SECRET_ACCESS_KEY = credentials('aws-secret-access-key')
    }

    stages {
        stage('Upload to S3') {
            steps {
                sh '''
                    echo "Checking tools..."
                    python3 --version
                    pip3 --version
                    ansible --version

                    echo "Installing Python dependencies..."
                    pip3 install --user boto3

                    echo "Running Ansible playbook..."
                    ansible-playbook playbooks/upload_to_s3.yml
                '''
            }
        }
    }

    post {
        success {
            echo 'Upload to S3 completed successfully'
        }
        failure {
            echo 'Upload to S3 failed'
        }
    }
}

