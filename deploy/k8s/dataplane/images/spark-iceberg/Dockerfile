# Spark with the Iceberg runtime already on the classpath.
#
# Build and push:
#   docker build -t <registry>/odf/spark-iceberg:3.5.1 .
#   docker push <registry>/odf/spark-iceberg:3.5.1
#
# Then set ODF_SPARK_IMAGE to that reference. Jobs submitted without an image
# use it, and the Iceberg catalog configuration comes from the engine profile.
FROM apache/spark:3.5.1

ARG ICEBERG_VERSION=1.6.1
ARG AWS_SDK_BUNDLE_VERSION=2.24.6

USER root

RUN set -eux; \
    curl -fsSL -o /opt/spark/jars/iceberg-spark-runtime.jar \
      "https://repo1.maven.org/maven2/org/apache/iceberg/iceberg-spark-runtime-3.5_2.12/${ICEBERG_VERSION}/iceberg-spark-runtime-3.5_2.12-${ICEBERG_VERSION}.jar"; \
    curl -fsSL -o /opt/spark/jars/iceberg-aws-bundle.jar \
      "https://repo1.maven.org/maven2/org/apache/iceberg/iceberg-aws-bundle/${ICEBERG_VERSION}/iceberg-aws-bundle-${ICEBERG_VERSION}.jar"; \
    curl -fsSL -o /opt/spark/jars/aws-sdk-bundle.jar \
      "https://repo1.maven.org/maven2/software/amazon/awssdk/bundle/${AWS_SDK_BUNDLE_VERSION}/bundle-${AWS_SDK_BUNDLE_VERSION}.jar"; \
    chmod 644 /opt/spark/jars/iceberg-spark-runtime.jar \
              /opt/spark/jars/iceberg-aws-bundle.jar \
              /opt/spark/jars/aws-sdk-bundle.jar

USER 185
