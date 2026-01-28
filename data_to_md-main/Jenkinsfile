pipeline {
    agent any
    
    environment {
        // 项目配置
        APP_NAME = 'data-to-md'
        DOCKER_IMAGE = 'data-to-md-app'
        
        // 服务器配置（在 Jenkins 凭据中配置）
        DEPLOY_SERVER = credentials('deploy-server-ip')
        DEPLOY_USER = credentials('deploy-server-user')
        DEPLOY_PATH = '/opt/data-to-md'
        
        // Docker 镜像仓库（可选，如使用私有仓库）
        // DOCKER_REGISTRY = 'your-registry.com'
        // DOCKER_CREDENTIALS = credentials('docker-registry-credentials')
    }
    
    options {
        // 构建超时时间
        timeout(time: 30, unit: 'MINUTES')
        // 保留最近10次构建
        buildDiscarder(logRotator(numToKeepStr: '10'))
        // 不允许并发构建
        disableConcurrentBuilds()
    }
    
    stages {
        stage('Checkout') {
            steps {
                echo '📥 拉取代码...'
                checkout scm
            }
        }
        
        stage('Prepare Environment') {
            steps {
                echo '🔧 准备环境配置...'
                script {
                    // 从 Jenkins 凭据获取敏感配置
                    withCredentials([
                        string(credentialsId: 'deepseek-api-key', variable: 'DEEPSEEK_API_KEY')
                    ]) {
                        // 生成 .env 文件
                        sh '''
                            cp .env.example .env.production
                            sed -i "s|DEEPSEEK_API_KEY=.*|DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY}|g" .env.production
                            sed -i "s|ENVIRONMENT=.*|ENVIRONMENT=production|g" .env.production
                        '''
                    }
                }
            }
        }
        
        stage('Build Docker Image') {
            steps {
                echo '🐳 构建 Docker 镜像...'
                sh '''
                    docker build -t ${DOCKER_IMAGE}:${BUILD_NUMBER} .
                    docker tag ${DOCKER_IMAGE}:${BUILD_NUMBER} ${DOCKER_IMAGE}:latest
                '''
            }
        }
        
        stage('Test') {
            steps {
                echo '🧪 运行测试...'
                sh '''
                    docker run --rm ${DOCKER_IMAGE}:${BUILD_NUMBER} python -m pytest tests/ -v --tb=short || true
                '''
            }
        }
        
        stage('Push Image') {
            when {
                // 仅在 main 分支推送镜像
                branch 'main'
            }
            steps {
                echo '📤 推送镜像到仓库...'
                script {
                    // 如果使用私有镜像仓库，取消下面的注释
                    // docker.withRegistry("https://${DOCKER_REGISTRY}", 'docker-registry-credentials') {
                    //     sh "docker push ${DOCKER_REGISTRY}/${DOCKER_IMAGE}:${BUILD_NUMBER}"
                    //     sh "docker push ${DOCKER_REGISTRY}/${DOCKER_IMAGE}:latest"
                    // }
                    
                    // 保存镜像为 tar 文件（用于直接传输到服务器）
                    sh '''
                        docker save ${DOCKER_IMAGE}:latest | gzip > ${DOCKER_IMAGE}.tar.gz
                    '''
                }
            }
        }
        
        stage('Deploy') {
            when {
                branch 'main'
            }
            steps {
                echo '🚀 部署到服务器...'
                script {
                    sshagent(credentials: ['deploy-server-ssh-key']) {
                        sh '''
                            # 传输文件到服务器
                            scp -o StrictHostKeyChecking=no ${DOCKER_IMAGE}.tar.gz ${DEPLOY_USER}@${DEPLOY_SERVER}:${DEPLOY_PATH}/
                            scp -o StrictHostKeyChecking=no docker-compose.yml ${DEPLOY_USER}@${DEPLOY_SERVER}:${DEPLOY_PATH}/
                            scp -o StrictHostKeyChecking=no .env.production ${DEPLOY_USER}@${DEPLOY_SERVER}:${DEPLOY_PATH}/.env
                            
                            # 在服务器上执行部署
                            ssh -o StrictHostKeyChecking=no ${DEPLOY_USER}@${DEPLOY_SERVER} << 'ENDSSH'
                                cd ${DEPLOY_PATH}
                                
                                # 加载镜像
                                docker load < ${DOCKER_IMAGE}.tar.gz
                                
                                # 停止旧容器
                                docker compose down || true
                                
                                # 启动新容器
                                docker compose up -d
                                
                                # 清理
                                rm -f ${DOCKER_IMAGE}.tar.gz
                                docker image prune -f
                                
                                # 健康检查
                                sleep 10
                                curl -f http://localhost:8000/api/v1/health || exit 1
                                
                                echo "✅ 部署完成!"
ENDSSH
                        '''
                    }
                }
            }
        }
    }
    
    post {
        success {
            echo '✅ 构建成功!'
            // 可添加通知，如钉钉、企业微信等
            // dingtalk(robot: 'dingtalk-robot', message: "✅ ${APP_NAME} 部署成功 - Build #${BUILD_NUMBER}")
        }
        failure {
            echo '❌ 构建失败!'
            // dingtalk(robot: 'dingtalk-robot', message: "❌ ${APP_NAME} 部署失败 - Build #${BUILD_NUMBER}")
        }
        always {
            // 清理工作空间中的临时文件
            sh 'rm -f *.tar.gz .env.production || true'
            cleanWs()
        }
    }
}
