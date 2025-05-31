FROM node:18-alpine

# Set working directory
WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci --only=production

# Copy source code
COPY . .

# Build the app
RUN npm run build

# Expose port
EXPOSE 3000

# Start the development server (or you could serve the built files with nginx)
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "3000"] 