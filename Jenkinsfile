pipeline {
  agent any

  options {
    disableConcurrentBuilds()
    timestamps()
    buildDiscarder(logRotator(numToKeepStr: '10'))
  }

  // Poll main every 2 minutes. Direct pushes are refused by Verify merge.
  triggers {
    pollSCM('H/2 * * * *')
  }

  environment {
    PATH = "/var/jenkins_home/bin:${env.PATH}"
    DOCKER_CONFIG = "/var/jenkins_home/.docker"
    GH_REPO = "ock666/Skyecoin"
    DEPLOY_DIR = "/mnt/user/appdata/skyecoin"
    HEALTH_URL = "http://192.168.0.51:5000/"
    COMPOSE_PROFILE = "--profile miner"
  }

  stages {
    stage('Checkout') {
      steps {
        checkout scm
      }
    }

    stage('Verify merge') {
      steps {
        withCredentials([usernamePassword(
          credentialsId: 'github-ock666',
          usernameVariable: 'GH_USER',
          passwordVariable: 'GH_TOKEN'
        )]) {
          sh '''
            set -euo pipefail
            sha=$(git rev-parse HEAD)
            prs=$(mktemp)
            curl -fsS -o "$prs" \
              -H "Authorization: Bearer $GH_TOKEN" \
              -H "Accept: application/vnd.github+json" \
              "https://api.github.com/repos/$GH_REPO/commits/$sha/pulls"
            if ! grep -q '"merged_at":[[:space:]]*"' "$prs"; then
              echo "Commit $sha is not associated with a merged pull request."
              echo "Direct pushes to main are not deployed; open a PR and merge it."
              rm -f "$prs"
              exit 1
            fi
            rm -f "$prs"
            echo "Commit $sha came from a merged pull request."
          '''
        }
      }
    }

    stage('Deploy') {
      steps {
        sh 'bash ./scripts/deploy.sh "$WORKSPACE" "$DEPLOY_DIR" "$HEALTH_URL" "$COMPOSE_PROFILE"'
      }
    }
  }

  post {
    success {
      echo 'skyecoin deployed'
    }
    failure {
      echo 'deploy failed, or this was a direct push to main'
    }
  }
}
