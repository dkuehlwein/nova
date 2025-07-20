"""
Docker container management utilities for Nova.

Handles restarting containers with new configurations using Docker API.
"""

from typing import Optional
from utils.logging import get_logger

logger = get_logger("docker-manager")


async def restart_llamacpp_container(model_file: str) -> bool:
    """
    Restart the llamacpp container with a new model file using Docker API.
    
    This approach:
    1. Sets the LLAMACPP_MODEL_FILE environment variable 
    2. Uses Docker Python SDK to restart the container via mounted docker.sock
    3. Much simpler than recreating - just restarts with new env var
    
    Args:
        model_file: The GGUF model file name (e.g., "phi-4-Q4_K_M.gguf")
        
    Returns:
        bool: True if restart was successful, False otherwise
    """
    try:
        logger.info(f"Restarting llamacpp container with model: {model_file}")
        
        import docker
        import os
        
        # Set environment variable so docker-compose picks it up on restart
        os.environ["LLAMACPP_MODEL_FILE"] = model_file
        logger.info(f"Set LLAMACPP_MODEL_FILE environment variable to: {model_file}")
        
        # Connect to Docker daemon via mounted socket
        client = docker.from_env()
        
        # Find the llamacpp container by name (try multiple naming patterns)
        container = None
        for container_name in ["nova-llamacpp-1", "nova_llamacpp_1", "llamacpp", "nova-llamacpp"]:
            try:
                container = client.containers.get(container_name)
                logger.info(f"Found llamacpp container: {container.name}")
                break
            except docker.errors.NotFound:
                continue
        
        if not container:
            logger.error("Could not find llamacpp container with any expected name")
            return False
        
        # We need to recreate the container to pick up new environment variables
        # Get the container configuration for recreation
        container_config = container.attrs
        image = container_config["Config"]["Image"]
        
        # Update environment variables
        env_vars = []
        if container_config["Config"]["Env"]:
            env_vars = [env for env in container_config["Config"]["Env"] if not env.startswith("LLAMACPP_MODEL_FILE=")]
        env_vars.append(f"LLAMACPP_MODEL_FILE={model_file}")
        
        # Get other configuration
        volumes = container_config["HostConfig"]["Binds"] or []
        network_mode = container_config["HostConfig"]["NetworkMode"]
        restart_policy = container_config["HostConfig"]["RestartPolicy"]
        
        # Hardcode nova-network for simplicity and reliability
        network_to_use = "nova-network"
        
        # Get port bindings
        port_bindings = {}
        if container_config["HostConfig"]["PortBindings"]:
            for container_port, host_bindings in container_config["HostConfig"]["PortBindings"].items():
                if host_bindings:
                    port_bindings[container_port] = host_bindings[0]["HostPort"]
        
        # Get devices (for GPU) - both Devices and DeviceRequests
        devices = container_config["HostConfig"]["Devices"] or []
        device_requests = container_config["HostConfig"]["DeviceRequests"] or []
        
        # Get labels (important for docker-compose integration)
        labels = container_config["Config"]["Labels"] or {}
        
        # Get command and modify it to use the environment variable
        cmd = container_config["Config"]["Cmd"]
        
        # Update the --model argument to use the new model file
        if cmd and isinstance(cmd, list):
            updated_cmd = []
            i = 0
            while i < len(cmd):
                if cmd[i] == "--model" and i + 1 < len(cmd):
                    # Replace the model path with the new model file
                    updated_cmd.append("--model")
                    updated_cmd.append(f"/models/{model_file}")
                    i += 2  # Skip the next argument (old model path)
                else:
                    updated_cmd.append(cmd[i])
                    i += 1
            cmd = updated_cmd
        
        # Stop and remove the existing container
        logger.info(f"Stopping and removing container: {container.name}")
        container.stop(timeout=30)
        container.remove()
        
        # Create new container with updated environment and proper network
        logger.info(f"Creating new container with updated environment on network: {network_to_use}")
        
        # Create container directly with the nova-network to avoid connection issues
        try:
            new_container = client.containers.create(
                image=image,
                command=cmd,
                environment=env_vars,
                volumes=volumes,
                ports=port_bindings,
                restart_policy=restart_policy,
                devices=devices,
                device_requests=device_requests,
                labels=labels,
                name=container.name,
                network=network_to_use  # Create directly with network instead of none + connect
            )
            logger.info(f"Successfully created container with network: {network_to_use}")
            
        except Exception as e:
            logger.error(f"Failed to create container: {e}")
            raise e
        
        # Start the container immediately after creation with retry logic
        logger.info("Starting the new container...")
        start_attempts = 3
        container_started = False
        
        for start_attempt in range(start_attempts):
            try:
                new_container.start()
                logger.info(f"Container start command executed (attempt {start_attempt + 1})")
                container_started = True
                break
            except Exception as start_error:
                logger.warning(f"Failed to start container (attempt {start_attempt + 1}/{start_attempts}): {start_error}")
                if start_attempt < start_attempts - 1:
                    await asyncio.sleep(2)
                else:
                    logger.error(f"Failed to start container after {start_attempts} attempts")
                    return False
        
        if not container_started:
            logger.error("Container could not be started")
            return False
        
        # Wait a moment for the container to fully start
        import asyncio
        await asyncio.sleep(5)  # Increased wait time for better reliability
        
        # Verify container is running with retries
        max_retries = 5  # Increased retries for better reliability
        for attempt in range(max_retries):
            new_container.reload()
            status = new_container.status
            
            if status == "running":
                logger.info(f"Successfully recreated and started llamacpp container with model: {model_file}")
                return True
            elif status == "created":
                # Container is created but not running - try to start it again
                logger.warning(f"Container in 'created' state, attempting to start again (attempt {attempt + 1})")
                try:
                    new_container.start()
                    await asyncio.sleep(3)
                except Exception as e:
                    logger.warning(f"Failed to start container in retry: {e}")
            elif attempt < max_retries - 1:
                logger.warning(f"Container status: {status}, checking again in 2 seconds... (attempt {attempt + 1}/{max_retries})")
                await asyncio.sleep(2)
            else:
                logger.error(f"Container recreation failed after {max_retries} attempts - final status: {status}")
                return False
        
    except Exception as e:
        logger.error(f"Failed to restart llamacpp container: {e}")
        return False


