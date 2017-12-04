node {
   stage "Checkout"
   checkout scm

   stage "Build"
   sh "docker-compose down -v --remove-orphans"
   sh "echo 'COMPOSE_PROJECT_NAME=${env.JOB_NAME}-${env.BUILD_ID}' > .env"
   sh "docker-compose build"
   sh "docker-compose run web python bootstrap.py"
   sh "docker-compose run web bin/buildout"

   stage "Test"
   sh "docker-compose run web bin/test"
   sh "docker-compose down -v --remove-orphans"

}
