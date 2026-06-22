pipeline {
    agent {
        label 'mac-machine'
    }

    options {
        skipDefaultCheckout(true)
    }

    environment {
        AWS_ACCESS_KEY_ID     = credentials('aws-access-key-id')
        AWS_SECRET_ACCESS_KEY = credentials('aws-secret-access-key')

        // AI failure summary (optional — uses Ollama only when nothing else is set):
        // AI_PROVIDER=openai
        // AI_MODEL=gpt-4o-mini
        // AI_API_KEY=credentials('openai-api-key')
        // AI_BASE_URL=https://api.openai.com/v1
        //
        // Ollama fallback env (only when no OpenAI-style config is present):
        // OLLAMA_URL=http://127.0.0.1:11434
        // OLLAMA_MODEL=llama3.2
        // OLLAMA_PULL_TIMEOUT=600
    }

    stages {
        stage('Clean Workspace') {
            steps {
                echo 'Deleting all workspace folders and files...'
                deleteDir()
            }
        }

        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Upload to S3') {
            steps {
                sh '''
                    set -euo pipefail

                    echo "Checking tools..."
                    python3 --version
                    pip3 --version
                    ansible --version

                    echo "Installing Python dependencies..."
                    pip3 install --user boto3

                    echo "Running Ansible playbook..."
                    nsible-playbook playbooks/upload_to_s3.yml
                '''
            }
        }
    }

    post {
        success {
            echo 'Upload to S3 completed successfully'
        }
        failure {
            script {
                def summary = summarizeFailureWithAi()
                echo "\n${summary}\n"
                currentBuild.description = summary.take(500)
            }
        }
    }
}

String summarizeFailureWithAi() {
    def logTail = currentBuild.rawBuild.getLog(250).join('\n').take(12000)
    writeFile file: 'failure-log.txt', text: logTail

    try {
        return sh(
            script: 'python3 scripts/jenkins_ai_summary.py',
            returnStdout: true
        ).trim()
    } catch (Exception err) {
        return "AI summary failed (${err.message}). Check ${env.BUILD_URL}console"
    }
}
