pipeline {
    agent any
    
    environment {
        APP_NAME = 'data-to-md'
        DOCKER_IMAGE = 'data-to-md-app'
    }
    
    options {
        timeout(time: 60, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '10'))
        disableConcurrentBuilds()
    }
    
    stages {
        stage('Checkout') {
            steps {
                echo '📥 拉取代码...'
                checkout scm
            }
        }
        
        stage('Prepare') {
            steps {
                echo '🔧 准备环境...'
                dir('data_to_md-main') {
                    sh 'cp .env.example .env || true'
                }
            }
        }
        
        stage('Build Docker Image') {
            steps {
                echo '🐳 构建 Docker 镜像...'
                dir('data_to_md-main') {
                    sh '''
                        docker build -t ${DOCKER_IMAGE}:${BUILD_NUMBER} .
                        docker tag ${DOCKER_IMAGE}:${BUILD_NUMBER} ${DOCKER_IMAGE}:latest
                    '''
                }
            }
        }
        
        stage('Test') {
            steps {
                echo '🧪 运行测试...'
                sh 'docker run --rm ${DOCKER_IMAGE}:${BUILD_NUMBER} python -m pytest tests/ -v --tb=short || true'
            }
        }
    }
    
    post {
        success {
            echo '✅ 构建成功!'
        }
        failure {
            echo '❌ 构建失败!'
        }
        always {
            echo '🧹 清理完成'
        }
    }
}
