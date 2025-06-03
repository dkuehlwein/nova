This is a [Next.js](https://nextjs.org) project bootstrapped with [`create-next-app`](https://nextjs.org/docs/app/api-reference/cli/create-next-app).

## Getting Started

First, run the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

You can start editing the page by modifying `app/page.tsx`. The page auto-updates as you edit the file.

This project uses [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) to automatically optimize and load [Geist](https://vercel.com/font), a new font family for Vercel.

## API Configuration

The Nova frontend automatically detects the backend API URL. However, if you encounter connection issues, you can manually configure it:

### Quick Setup for WSL2

For WSL2 users, there's an automated setup script in the root directory:

```bash
cd scripts
./setup-wsl2.sh
```

This script will:
- Detect your WSL2 IP address
- Test backend connectivity
- Update the root `.env` file automatically
- Provide troubleshooting guidance

### Manual Configuration

#### For WSL2 Users

If you're running the backend in WSL2 and the frontend in Windows:

1. Find your WSL2 IP address:
   ```bash
   hostname -I
   ```

2. Add to the root `.env` file (create if it doesn't exist):
   ```bash
   # .env (in nova/ root directory)
   NEXT_PUBLIC_API_URL=http://YOUR_WSL2_IP:8000
   ```

   Replace `YOUR_WSL2_IP` with the actual IP from step 1.

3. Restart the frontend development server.

#### For Docker Users

If running the entire stack in Docker:

```bash
# .env (in nova/ root directory)
NEXT_PUBLIC_API_URL=http://localhost:8000
```

#### For Production

Set the production API URL:

```bash
# .env (in nova/ root directory)
NEXT_PUBLIC_API_URL=https://your-backend-domain.com
```

## Troubleshooting

### Backend Connection Issues

1. **Check if backend is running:**
   ```bash
   curl http://localhost:8000/health
   ```

2. **Check the browser console** for auto-detection logs. Look for:
   - ✅ Backend detected at: [URL]
   - ⚠️ Could not auto-detect backend URL

3. **CORS Issues:** If you see CORS errors, ensure the backend is configured to allow your frontend origin.

4. **WSL2 IP Changes:** If your WSL2 IP changes (after restart), run the setup script again:
   ```bash
   cd scripts && ./setup-wsl2.sh
   ```

### Environment Variables

- `NEXT_PUBLIC_API_URL`: Override the auto-detected backend URL
- All `NEXT_PUBLIC_*` variables are exposed to the browser

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.
