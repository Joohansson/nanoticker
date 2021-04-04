FROM node:14

WORKDIR /usr/src/app
RUN chown node:node .
USER node

# Prepare environment
COPY ./package*.json ./
RUN npm install

# Copy source files
COPY ./ .

EXPOSE 9950

CMD [ "node", "json-cache.js" ]