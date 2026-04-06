FROM rabbitmq:4.0-management-alpine

# Adiciona o plugin rabbitmq_delayed_message_exchange
# v4.0.2 é compatível com a série RabbitMQ 4.0.x
RUN apk add --no-cache curl \
    && curl -L https://github.com/rabbitmq/rabbitmq-delayed-message-exchange/releases/download/v4.0.7/rabbitmq_delayed_message_exchange-v4.0.7.ez > /opt/rabbitmq/plugins/rabbitmq_delayed_message_exchange-v4.0.7.ez \
    && rabbitmq-plugins enable --offline rabbitmq_delayed_message_exchange \
    && apk del curl
