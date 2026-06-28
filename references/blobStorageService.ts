import { BlobServiceClient, ContainerClient } from "@azure/storage-blob";
import config from "./config";
import logger from "./logger";
import fs from "fs";

/**
 * Azure Blob Storage utility class for handling file operations
 */
export class BlobStorageService {
  private blobServiceClient: BlobServiceClient;
  private containerClient: ContainerClient;

  constructor() {
    if (!config.azure.storageAccount || !config.azure.storageKey || !config.azure.containerName) {
      throw new Error("Azure Storage configuration is missing");
    }

    const connectionString = `DefaultEndpointsProtocol=https;AccountName=${config.azure.storageAccount};AccountKey=${config.azure.storageKey};EndpointSuffix=core.windows.net`;
    this.blobServiceClient = BlobServiceClient.fromConnectionString(connectionString);
    this.containerClient = this.blobServiceClient.getContainerClient(config.azure.containerName);
  }

  /**
   * Uploads a JSON file to Azure Blob Storage
   * @param content - The content to upload
   * @param fileName - The name of the file
   * @returns The URL of the uploaded blob
   */
  async uploadJsonFile(content: any, fileName: string): Promise<string> {
    try {
      const blobClient = this.containerClient.getBlockBlobClient(fileName);
      const jsonString = JSON.stringify(content, null, 2);

      await blobClient.upload(jsonString, jsonString.length, {
        blobHTTPHeaders: {
          blobContentType: "application/json",
        },
      });

      logger.info(`Successfully uploaded ${fileName} to Azure Blob Storage`);
      return blobClient.url;
    } catch (error) {
      logger.error(`Error uploading to Azure Blob Storage: ${(error as Error).message}`);
      throw new Error(`Failed to upload to Azure Blob Storage: ${(error as Error).message}`);
    }
  }

  /**
   * Uploads an Excel file to Azure Blob Storage
   * @param buffer - The file buffer to upload
   * @param originalName - Original name of the file
   * @returns The URL of the uploaded blob
   */
  async uploadExcelFile(buffer: Buffer, originalName: string): Promise<string> {
    try {
      const fileName = this.generateExcelFileName(originalName);
      const blobClient = this.containerClient.getBlockBlobClient(fileName);

      await blobClient.upload(buffer, buffer.length, {
        blobHTTPHeaders: {
          blobContentType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        },
      });

      logger.info(`Successfully uploaded Excel file ${fileName} to Azure Blob Storage`);
      return blobClient.url;
    } catch (error) {
      logger.error(`Error uploading Excel file to Azure Blob Storage: ${(error as Error).message}`);
      throw new Error(`Failed to upload Excel file to Azure Blob Storage: ${(error as Error).message}`);
    }
  }

  /**
   * Uploads an Excel file from a local file path to Azure Blob Storage
   * @param filePath - Local path to the Excel file on disk
   * @param originalName - Original name of the file
   * @returns The URL of the uploaded blob
   */
  async uploadExcelFileFromPath(filePath: string, originalName: string): Promise<string> {
    const buffer = fs.readFileSync(filePath);
    return this.uploadExcelFile(buffer, originalName);
  }

  /**
   * Generates a filename for the log file based on the current date and time
   * @returns Formatted filename
   */
  static generateLogFileName(): string {
    const now = new Date();
    const dateStr = now.toISOString().split("T")[0]; // YYYY-MM-DD
    const timeStr = now.toTimeString().split(" ")[0].replace(/:/g, "-"); // HH-MM-SS
    return `${dateStr}_${timeStr}.json`;
  }

  /**
   * Generates a filename for the Excel file based on the current date and original filename
   * @param originalName - Original name of the file
   * @returns Formatted filename with path
   */
  private generateExcelFileName(originalName: string): string {
    // Convert the current date and time to IST (UTC+5:30)
    const now = new Date();
    const istTime = new Date(now.getTime() + 5.5 * 60 * 60 * 1000); // Add 5.5 hours in milliseconds
    const dateStr = istTime.toISOString().split("T")[0]; // YYYY-MM-DD
    const timeStr = istTime.toISOString().split("T")[1].split(".")[0].replace(/:/g, "-"); // HH-MM-SS
    const baseName = originalName.replace(/\.[^/.]+$/, ""); // Remove extension

    return `${dateStr}/${baseName}_${timeStr}.xlsm`;
  }
}
